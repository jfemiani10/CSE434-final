"""Central configuration: models, experiment conditions, budgets.

Switching models should only ever mean changing a key here or passing a
different --model flag; no other code should hard-code a model name.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str            # short name used on the command line and in logs
    backend: str        # "gemini" | "openai_compat"
    model_id: str       # provider's model id / Ollama tag
    base_url: str | None = None   # for openai_compat backends
    context_window: int = 8192    # tokens; prompts longer than this get truncated
    notes: str = ""


OLLAMA_URL = "http://localhost:11434/v1"

MODELS: dict[str, ModelSpec] = {
    # Closed model. Pin an exact version id before the real experiment runs.
    "gemini": ModelSpec("gemini", "gemini", "gemini-flash-latest", context_window=1_000_000),
    # Open models, served by Ollama (OpenAI-compatible API). Ollama's default
    # tags are 4-bit quantized (Q4_K_M); report that in the paper.
    "qwen": ModelSpec(
        "qwen", "openai_compat", "qwen2.5-coder:7b", OLLAMA_URL, 8192,
        notes="Qwen2.5-Coder-7B-Instruct, default open model (pending approval)",
    ),
    "llama2": ModelSpec(
        "llama2", "openai_compat", "llama2:7b-chat", OLLAMA_URL, 4096,
        notes="LLaMA-2-7B-chat, named in the proposal; only 4k context, so long RAG prompts won't fit",
    ),
}

DEFAULT_OPEN_MODEL = "qwen"
TEMPERATURE = 0.2
SEED = 434
RENDER_TIMEOUT_S = 120
