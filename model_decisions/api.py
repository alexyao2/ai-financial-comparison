"""OpenAI-compatible HTTP clients, response cache, and shared budget reservations."""
import hashlib
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import urllib.request
import urllib.error

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}
MAX_OUTPUT = 2048
CAP = 5.0


class Budget:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, reserved REAL, actual REAL, status TEXT)")

    def reserve(self, key, amount):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid API cost reservation")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT status FROM calls WHERE id=?", (key,)).fetchone()
            if existing and existing[0] != 'rate_limited':
                raise RuntimeError("This request already has a reservation but no usable cache. Inspect the ledger; do not retry blindly.")
            spent = db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM calls").fetchone()[0]
            if spent + amount > CAP:
                raise RuntimeError(f"$5 project budget would be exceeded (committed ${spent:.4f})")
            db.execute("INSERT OR REPLACE INTO calls VALUES (?,?,NULL,'reserved')", (key, amount))

    def rate_limited(self, key):
        # HTTP 429 rejected generation; unlike a timeout, this can safely be retried later.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE calls SET actual=0, status='rate_limited' WHERE id=?", (key,))

    def settle(self, key, amount):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid reported API usage")
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT reserved FROM calls WHERE id=?", (key,)).fetchone()
            if row is None:
                raise RuntimeError("Missing reservation")
            db.execute("UPDATE calls SET actual=?, status='complete' WHERE id=?", (amount, key))
        if amount > row[0] + 1e-9:
            raise RuntimeError("Usage exceeded conservative reservation; verify pricing before continuing")

    def committed(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM calls").fetchone()[0]


def provider_settings(provider):
    prefix = provider.upper()
    result = {"provider": provider, "model": os.getenv(prefix + "_MODEL", ""),
              "key": os.getenv(prefix + "_API_KEY", "")}
    if not result["model"] or not result["key"]:
        raise ValueError(f"Set {prefix}_MODEL and {prefix}_API_KEY in .env")
    for side in ("input", "output"):
        value = os.getenv(prefix + "_" + side.upper() + "_PRICE", "")
        try:
            price = float(value)
        except ValueError:
            raise ValueError(f"Set verified {prefix}_{side.upper()}_PRICE (USD/million tokens)") from None
        if not math.isfinite(price) or price < 0:
            raise ValueError("API prices must be finite and nonnegative")
        result[side] = price
    return result


class APIClient:
    def __init__(self, provider, root):
        self.settings = provider_settings(provider)
        self.provider = provider
        self.root = Path(root)
        self.budget = Budget(self.root / ".cache" / "api_budget.sqlite3")
        self.cache = self.root / ".cache" / "responses"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.last_metadata = {}

    def decide(self, system, packet):
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(packet, sort_keys=True, allow_nan=False)}]
        body = {"model": self.settings["model"], "messages": messages,
                "response_format": {"type": "json_object"}}
        body["max_tokens" if self.provider == "gemini" else "max_completion_tokens"] = MAX_OUTPUT
        encoded = json.dumps(body, sort_keys=True, allow_nan=False).encode()
        key = hashlib.sha256(self.provider.encode() + encoded).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists():
            saved = json.loads(path.read_text())
            self.last_metadata = {**saved["metadata"], "cache_hit": True}
            return json.loads(saved["response"]["choices"][0]["message"]["content"])
        # UTF-8 byte count plus framing margin is deliberately conservative.
        estimated = ((len(encoded) + 4096) * self.settings["input"] + MAX_OUTPUT * self.settings["output"]) / 1_000_000
        self.budget.reserve(key, estimated)
        request = urllib.request.Request(ENDPOINTS[self.provider], data=encoded,
            headers={"Authorization": "Bearer " + self.settings["key"], "Content-Type": "application/json"})
        # No automatic retries. Uncertain/failed requests keep their reservation.
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                self.budget.rate_limited(key)
                raise RuntimeError("Provider rate limit reached. Wait for quota reset and rerun; completed responses are cached.") from None
            raise
        usage = raw.get("usage", {})
        actual = None
        if "prompt_tokens" in usage and "completion_tokens" in usage:
            actual = (usage["prompt_tokens"] * self.settings["input"] + usage["completion_tokens"] * self.settings["output"]) / 1_000_000
        metadata = {"provider": self.provider, "requested_model": self.settings["model"],
                    "returned_model": raw.get("model"), "usage": usage,
                    "cost_usd": actual, "reserved_usd": estimated, "cache_hit": False}
        # Persist raw output before parsing, so invalid JSON is still auditable.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"response": raw, "metadata": metadata}, indent=2))
        temporary.replace(path)
        self.last_metadata = metadata
        if actual is not None:
            self.budget.settle(key, actual)
        return json.loads(raw["choices"][0]["message"]["content"])
