"""Model requests, caching, and the shared API budget."""
import hashlib
from contextlib import closing, contextmanager
import json
import math
import os
from pathlib import Path
import sqlite3
import urllib.request
import urllib.error
import uuid

ENDPOINTS = {
    "nvidia_nemotron": "https://integrate.api.nvidia.com/v1/chat/completions",
    "nvidia_deepseek": "https://integrate.api.nvidia.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}
MAX_OUTPUT = 2048
CAP = 5.0
COMMITTED_SQL = "SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM calls"


def parse_response(raw):
    choice = raw["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("Output token limit reached before completion; increase the output token limit.")
    content = choice["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Model returned no final answer; inspect the cached response.")
    return json.loads(content)


class Budget:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, reserved REAL, actual REAL, status TEXT)")

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            yield db

    def reserve(self, key, amount, retry_free=False):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid API cost reservation")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT status, reserved, actual FROM calls WHERE id=?", (key,)).fetchone()
            if existing and existing[0] != 'rate_limited':
                if retry_free and amount == 0 and existing == ('reserved', 0, None):
                    # Preserve the uncertain attempt when explicitly retrying a free call.
                    key = key + "-retry-" + uuid.uuid4().hex
                else:
                    raise RuntimeError("Request already reserved without a cached response; inspect the ledger before retrying.")
            spent = db.execute(COMMITTED_SQL).fetchone()[0]
            if spent + amount > CAP:
                raise RuntimeError(f"$5 project budget would be exceeded (committed ${spent:.4f})")
            db.execute("INSERT OR REPLACE INTO calls VALUES (?,?,NULL,'reserved')", (key, amount))
        return key

    def rate_limited(self, key):
        with self.connect() as db:
            db.execute("UPDATE calls SET actual=0, status='rate_limited' WHERE id=?", (key,))

    def settle(self, key, amount):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid reported API usage")
        with self.connect() as db:
            row = db.execute("SELECT reserved FROM calls WHERE id=?", (key,)).fetchone()
            if row is None:
                raise RuntimeError("Missing reservation")
            db.execute("UPDATE calls SET actual=?, status='complete' WHERE id=?", (amount, key))
        if amount > row[0] + 1e-9:
            raise RuntimeError("Usage exceeded reservation; verify pricing.")

    def committed(self):
        with self.connect() as db:
            return db.execute(COMMITTED_SQL).fetchone()[0]


def provider_settings(provider):
    prefix = provider.upper()
    price_prefix = "NVIDIA" if provider.startswith("nvidia_") else prefix
    key_variable = price_prefix + "_API_KEY"
    result = {"provider": provider, "model": os.getenv(prefix + "_MODEL", ""),
              "key": os.getenv(key_variable, "")}
    if not result["model"] or not result["key"]:
        raise ValueError(f"Set {prefix}_MODEL and {key_variable} in .env")
    for side in ("input", "output"):
        value = os.getenv(price_prefix + "_" + side.upper() + "_PRICE", "")
        try:
            price = float(value)
        except ValueError:
            raise ValueError(f"Set verified {price_prefix}_{side.upper()}_PRICE (USD/million tokens)") from None
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
        self.max_output = int(os.getenv(f"{provider.upper()}_MAX_OUTPUT_TOKENS", str(MAX_OUTPUT)))
        if self.max_output <= 0:
            raise ValueError("Output token limit must be positive")
        self.timeout = float(os.getenv("API_TIMEOUT_SECONDS", "60"))
        if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 600:
            raise ValueError("API_TIMEOUT_SECONDS must be between 1 and 600")

    def cost(self, input_tokens, output_tokens):
        return (input_tokens * self.settings["input"] + output_tokens * self.settings["output"]) / 1_000_000

    def save_error(self, attempt, details):
        folder = self.root / ".cache" / "errors"
        folder.mkdir(parents=True, exist_ok=True)
        details.update(provider=self.provider, model=self.settings["model"], attempt=attempt)
        text = json.dumps(details, indent=2).replace(self.settings["key"], "[REDACTED]")
        path = folder / f"{attempt}.json"
        path.write_text(text)
        return path

    def decide(self, system, packet):
        token_parameter = "max_completion_tokens" if self.provider == "groq" else "max_tokens"
        body = {
            "model": self.settings["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(packet, sort_keys=True, allow_nan=False)},
            ],
            "response_format": {"type": "json_object"},
            token_parameter: self.max_output,
        }
        encoded = json.dumps(body, sort_keys=True, allow_nan=False).encode()
        key = hashlib.sha256(self.provider.encode() + encoded).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists():
            saved = json.loads(path.read_text())
            self.last_metadata = {**saved["metadata"], "cache_hit": True}
            return parse_response(saved["response"])
        # UTF-8 byte count plus framing margin is deliberately conservative.
        estimated = self.cost(len(encoded) + 4096, self.max_output)
        attempt = self.budget.reserve(key, estimated,
            retry_free=os.getenv("API_RETRY_FREE_FAILURES") == "1")
        request = urllib.request.Request(ENDPOINTS[self.provider], data=encoded,
            headers={"Authorization": "Bearer " + self.settings["key"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = error.read(8192).decode("utf-8", errors="replace")
            except Exception:
                detail = "Unable to read error response"
            path = self.save_error(attempt, {"http_status": error.code, "body": detail})
            if error.code == 429:
                self.budget.rate_limited(attempt)
                raise RuntimeError("Rate limited; rerun after quota reset. Completed responses are cached.") from None
            raise RuntimeError(f"{self.provider}: HTTP {error.code}; details: {path}") from None
        except TimeoutError:
            path = self.save_error(attempt, {"error": "timeout", "timeout_seconds": self.timeout})
            raise TimeoutError(f"{self.provider}: socket timeout ({self.timeout:g}s). Details: {path}") from None
        usage = raw.get("usage", {})
        actual = None
        if "prompt_tokens" in usage and "completion_tokens" in usage:
            actual = self.cost(usage["prompt_tokens"], usage["completion_tokens"])
        metadata = {"provider": self.provider, "requested_model": self.settings["model"],
                    "returned_model": raw.get("model"), "usage": usage,
                    "cost_usd": actual, "reserved_usd": estimated, "cache_hit": False}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"response": raw, "metadata": metadata}, indent=2))
        temporary.replace(path)
        self.last_metadata = metadata
        if actual is not None:
            self.budget.settle(attempt, actual)
        return parse_response(raw)
