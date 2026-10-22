"""Model requests, response caching, and bounded retries."""
import hashlib
import json
import math
import os
import ssl
import certifi
from pathlib import Path
import time
import urllib.request
import urllib.error
import uuid
from prompts.decision_schema import DECISION_JSON_SCHEMA

ENDPOINTS = {
    "nvidia_nemotron": "https://integrate.api.nvidia.com/v1/chat/completions",
    "nvidia_google": "https://integrate.api.nvidia.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}
MAX_OUTPUT = 2048
MAX_ATTEMPTS = 3


def parse_response(raw):
    choice = raw["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("Output token limit reached before completion; increase the output token limit.")
    content = choice["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Model returned no final answer; inspect the cached response.")
    return json.loads(content)


def provider_settings(provider):
    prefix = provider.upper()
    key_prefix = "NVIDIA" if provider.startswith("nvidia_") else prefix
    key_variable = key_prefix + "_API_KEY"
    result = {"provider": provider, "model": os.getenv(prefix + "_MODEL", ""),
              "key": os.getenv(key_variable, "")}
    if not result["model"] or not result["key"]:
        raise ValueError(f"Set {prefix}_MODEL and {key_variable} in .env")
    return result


class APIClient:
    def __init__(self, provider, root, fresh=False):
        self.settings = provider_settings(provider)
        self.provider = provider
        self.root = Path(root)
        self.cache = self.root / ".cache" / "responses"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.fresh = fresh
        self.last_metadata = {}
        self.max_output = int(os.getenv(f"{provider.upper()}_MAX_OUTPUT_TOKENS", str(MAX_OUTPUT)))
        if self.max_output <= 0:
            raise ValueError("Output token limit must be positive")
        self.timeout = float(os.getenv("API_TIMEOUT_SECONDS", "60"))
        if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 600:
            raise ValueError("API_TIMEOUT_SECONDS must be between 1 and 600")

        self.retry_delay = float(os.getenv("API_RETRY_DELAY_SECONDS", "5"))
        if not math.isfinite(self.retry_delay) or self.retry_delay <= 0:
            raise ValueError("API_RETRY_DELAY_SECONDS must be positive")

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
        if self.provider == "groq" and self.settings["model"] in (
                "openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            body["response_format"] = {
                "type": "json_schema", "json_schema": {
                    "name": "portfolio_decision", "strict": True,
                    "schema": DECISION_JSON_SCHEMA,
                },
            }
        encoded = json.dumps(body, sort_keys=True, allow_nan=False).encode()
        key = hashlib.sha256(self.provider.encode() + encoded).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists() and not self.fresh:
            saved = json.loads(path.read_text())
            self.last_metadata = {k: v for k, v in saved["metadata"].items()
                                  if k not in ("cost_usd", "reserved_usd")}
            self.last_metadata["cache_hit"] = True
            return parse_response(saved["response"])
        request = urllib.request.Request(ENDPOINTS[self.provider], data=encoded,
            headers={"Authorization": "Bearer " + self.settings["key"],
                     "Content-Type": "application/json",
                     "User-Agent": "ai-financial-comparison/1.0"})
        for number in range(MAX_ATTEMPTS):
            attempt = key + "-" + uuid.uuid4().hex
            try:
                with urllib.request.urlopen(request, timeout=self.timeout,
                        context=ssl.create_default_context(cafile=certifi.where())) as response:
                    raw = json.load(response)
                break
            except urllib.error.HTTPError as error:
                try:
                    detail = error.read(8192).decode("utf-8", errors="replace")
                except Exception:
                    detail = "Unable to read error response"
                error_path = self.save_error(attempt, {"http_status": error.code, "body": detail})
                if error.code not in (408, 429, 500, 502, 503, 504) or number == MAX_ATTEMPTS - 1:
                    raise RuntimeError(f"{self.provider}: HTTP {error.code}; details: {error_path}") from None
            except TimeoutError:
                error_path = self.save_error(attempt, {"error": "timeout", "timeout_seconds": self.timeout})
                if number == MAX_ATTEMPTS - 1:
                    raise TimeoutError(f"{self.provider}: socket timeout ({self.timeout:g}s). Details: {error_path}") from None
            delay = self.retry_delay * 2**number
            print(f"{self.provider}: temporary failure; retry {number + 2}/{MAX_ATTEMPTS} in {delay}s", flush=True)
            time.sleep(delay)
        usage = raw.get("usage", {})
        metadata = {"provider": self.provider, "requested_model": self.settings["model"],
                    "returned_model": raw.get("model"), "usage": usage,
                    "attempts": number + 1, "cache_hit": False}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"response": raw, "metadata": metadata}, indent=2))
        temporary.replace(path)
        self.last_metadata = metadata
        return parse_response(raw)
