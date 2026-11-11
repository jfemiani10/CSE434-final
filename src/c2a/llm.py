"""One interface for every model: `LLM(key).generate(prompt, system=...)`.

- Backends: Gemini (google-genai SDK) and any OpenAI-compatible server (Ollama).
- Disk cache: identical requests return the saved response instead of calling
  the API again. Reruns are free and reproducible, and a crash halfway through
  an experiment doesn't waste the calls already made.
- Retries with exponential backoff on rate limits (429) and server errors (5xx),
  which the Gemini free tier hits regularly.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

from c2a.config import CACHE_DIR, MAX_OUTPUT_TOKENS, MODELS, ROOT, SEED, TEMPERATURE, ModelSpec

load_dotenv(ROOT / ".env")

MAX_RETRIES = 6
RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}
REQUEST_TIMEOUT_S = 180


@dataclass
class LLMResponse:
    text: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    thinking_tokens: int
    latency_s: float     # time of the original API call, even when served from cache
    cached: bool = False
    model_version: str | None = None  # what the provider says actually served the request


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """Daily quota used up. Retrying within this run is pointless; rerun later (cached calls are kept)."""


class LLM:
    def __init__(self, model_key: str, use_cache: bool = True):
        if model_key not in MODELS:
            raise KeyError(f"Unknown model {model_key!r}; options: {list(MODELS)}")
        self.spec: ModelSpec = MODELS[model_key]
        self.use_cache = use_cache
        self._client = None  # created lazily, so cache hits never need a key or a server

    # -- public ---------------------------------------------------------------
    def generate(self, prompt: str, system: str | None = None,
                 json_schema: type | None = None) -> LLMResponse:
        """Send one prompt. `json_schema` (a pydantic model class) asks for JSON output."""
        key = self._cache_key(prompt, system, json_schema)
        path = CACHE_DIR / f"{key}.json"
        if self.use_cache and path.exists():
            data = json.loads(path.read_text())
            data.setdefault("model_version", None)  # older cache entries
            return LLMResponse(**{**data, "cached": True})

        resp = self._with_retries(lambda: self._call(prompt, system, json_schema))
        if self.use_cache:
            _atomic_write(path, json.dumps(asdict(resp), indent=1))
        return resp

    # -- backends -------------------------------------------------------------
    def _call(self, prompt: str, system: str | None, json_schema: type | None) -> LLMResponse:
        if self.spec.backend == "gemini":
            return self._call_gemini(prompt, system, json_schema)
        if self.spec.backend == "openai_compat":
            return self._call_openai_compat(prompt, system, json_schema)
        raise ValueError(f"Unknown backend {self.spec.backend}")

    def _call_gemini(self, prompt, system, json_schema) -> LLMResponse:
        from google import genai
        from google.genai import types

        if self._client is None:
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise LLMError("GEMINI_API_KEY is not set (copy .env.example to .env and fill it in)")
            self._client = genai.Client(api_key=key, http_options=types.HttpOptions(
                timeout=REQUEST_TIMEOUT_S * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),  # we retry ourselves
            ))
        cfg = types.GenerateContentConfig(
            temperature=TEMPERATURE, seed=SEED, max_output_tokens=MAX_OUTPUT_TOKENS,
            system_instruction=system,
        )
        if self.spec.thinking_level:
            cfg.thinking_config = types.ThinkingConfig(thinking_level=self.spec.thinking_level.upper())
        if json_schema is not None:
            cfg.response_mime_type = "application/json"
            cfg.response_schema = json_schema

        t0 = time.time()
        r = self._client.models.generate_content(model=self.spec.model_id, contents=prompt, config=cfg)
        latency = time.time() - t0
        text = r.text
        if not text:
            reason = r.candidates[0].finish_reason if r.candidates else "no candidates"
            raise LLMError(f"Empty response from {self.spec.model_id} (finish_reason={reason})")
        u = r.usage_metadata
        return LLMResponse(text, self.spec.model_id, u.prompt_token_count or 0,
                           u.candidates_token_count or 0, u.thoughts_token_count or 0, latency,
                           model_version=getattr(r, "model_version", None))

    def _call_openai_compat(self, prompt, system, json_schema) -> LLMResponse:
        from openai import OpenAI

        if self._client is None:
            self._client = OpenAI(base_url=self.spec.base_url, api_key=os.environ.get("OPENAI_API_KEY", "ollama"),
                                  timeout=REQUEST_TIMEOUT_S, max_retries=0)
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        kwargs = {"response_format": {"type": "json_object"}} if json_schema is not None else {}
        t0 = time.time()
        r = self._client.chat.completions.create(
            model=self.spec.model_id, messages=messages, temperature=TEMPERATURE, seed=SEED,
            max_tokens=MAX_OUTPUT_TOKENS, **kwargs)
        latency = time.time() - t0
        u = r.usage
        return LLMResponse(r.choices[0].message.content or "", self.spec.model_id,
                           u.prompt_tokens if u else 0, u.completion_tokens if u else 0, 0, latency,
                           model_version=getattr(r, "model", None))

    # -- helpers --------------------------------------------------------------
    def _with_retries(self, fn):
        for attempt in range(MAX_RETRIES):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 - classify below
                code = _status_code(e)
                if code == 429 and "PerDay" in str(e):
                    # Per-minute limits clear in seconds; a per-day limit won't clear this run.
                    raise QuotaExhausted(f"{self.spec.model_id}: daily request quota exhausted. "
                                         f"Wait for the reset or use a paid key. ({str(e)[:200]})") from e
                if code not in RETRYABLE_CODES or attempt == MAX_RETRIES - 1:
                    raise
                # Exponential backoff with jitter: ~5s, 10s, 20s, 40s, 60s.
                wait = min(60, 5 * 2 ** attempt) * (0.8 + 0.4 * random.random())
                print(f"[llm] {self.spec.model_id}: HTTP {code}, retrying in {wait:.0f}s "
                      f"({attempt + 1}/{MAX_RETRIES - 1})", flush=True)
                time.sleep(wait)

    def _cache_key(self, prompt: str, system: str | None, json_schema: type | None) -> str:
        s = self.spec
        blob = json.dumps({
            "model": s.model_id, "backend": s.backend, "thinking": s.thinking_level,
            "temperature": TEMPERATURE, "seed": SEED, "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system, "prompt": prompt,
            "schema": json_schema.__name__ if json_schema else None,
        }, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _status_code(e: Exception) -> int | None:
    for attr in ("code", "status_code"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    name = type(e).__name__
    if name in {"APIConnectionError", "APITimeoutError", "ReadTimeout", "ConnectTimeout"}:
        return 503  # transient network trouble: retry
    return None


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + rename so parallel workers never read half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(text)
    tmp.replace(path)
