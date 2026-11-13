"""Central configuration: models, experiment conditions, budgets, paths.

Switching models should only ever mean changing a key here or passing a
different --model flag; no other code should hard-code a model name.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CONCEPTS_PATH = DATA_DIR / "concepts.json"
STORYBOARD_DIR = DATA_DIR / "storyboards"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
OUTPUTS_DIR = ROOT / "outputs"
LOGS_DIR = ROOT / "results" / "logs"
TABLES_DIR = ROOT / "results" / "tables"
CACHE_DIR = ROOT / ".cache" / "llm"


# --- models ------------------------------------------------------------------
@dataclass(frozen=True)
class ModelSpec:
    key: str            # short name used on the command line and in logs
    backend: str        # "gemini" | "openai_compat"
    model_id: str       # provider's model id / Ollama tag
    base_url: str | None = None   # for openai_compat backends
    context_window: int = 8192    # tokens; prompts longer than this get truncated
    thinking_level: str | None = None  # Gemini 3.x only: minimal | low | medium | high
    notes: str = ""


OLLAMA_URL = "http://localhost:11434/v1"

MODELS: dict[str, ModelSpec] = {
    # Closed model. Pinned to an exact version so results don't drift when
    # Google repoints an alias. Checked 2026-11-10: gemini-2.5-flash is retired
    # for new keys, and gemini-3.8-flash timed out (504) even on a one-word prompt.
    "gemini": ModelSpec(
        "gemini", "gemini", "gemini-3.5-flash", context_window=1_000_000,
        thinking_level="low",
        notes="Gemini 3.x 'thinks' before answering; level fixed so it's the same in every run",
    ),
    # Codegen models for the ablation: the same model family at two sizes, so
    # parameter count is the only difference. Served by Ollama (OpenAI-compatible
    # API). Tags pin the exact 4-bit quantization (Q4_K_M) so every machine pulls
    # identical weights; report the quantization in the paper.
    "qwen7b": ModelSpec(
        "qwen7b", "openai_compat", "qwen2.5-coder:7b-instruct-q4_K_M", OLLAMA_URL, 8192,
        notes="Qwen2.5-Coder-7B-Instruct, ~4.7 GB",
    ),
    "qwen3b": ModelSpec(
        "qwen3b", "openai_compat", "qwen2.5-coder:3b-instruct-q4_K_M", OLLAMA_URL, 8192,
        notes="Qwen2.5-Coder-3B-Instruct, ~1.9 GB",
    ),
    "llama2": ModelSpec(
        "llama2", "openai_compat", "llama2:7b-chat", OLLAMA_URL, 4096,
        notes="LLaMA-2-7B-chat, named in the proposal; only 4k context, so long RAG prompts won't fit",
    ),
}

DEFAULT_OPEN_MODEL = "qwen7b"
# The planner always uses the same model, so every condition and every codegen
# model gets the same storyboard for a concept (fairness rule in CLAUDE.md).
PLANNER_MODEL = "gemini"

TEMPERATURE = 0.2
SEED = 434
MAX_OUTPUT_TOKENS = 8192


# --- experiment conditions ---------------------------------------------------
@dataclass(frozen=True)
class Condition:
    key: str
    few_shot: bool = False
    rag: bool = False
    error_repair: bool = False
    layout_repair: bool = False

    @property
    def max_render_attempts(self) -> int:
        # Conditions without repair get exactly one render attempt.
        return 1 + MAX_ERROR_REPAIRS if self.error_repair else 1


MAX_ERROR_REPAIRS = 3    # N in CLAUDE.md
MAX_LAYOUT_REPAIRS = 2   # M in CLAUDE.md

CONDITIONS: dict[str, Condition] = {c.key: c for c in [
    Condition("zero_shot"),
    Condition("zero_shot_repair", error_repair=True),
    Condition("few_shot", few_shot=True),
    Condition("rag", few_shot=True, rag=True),
    Condition("rag_repair", few_shot=True, rag=True, error_repair=True),
    Condition("rag_repair_layout", few_shot=True, rag=True, error_repair=True, layout_repair=True),
]}

# Which conditions the code can actually run yet. Grows as phases land.
IMPLEMENTED_CONDITIONS = {"zero_shot", "zero_shot_repair"}


# --- rendering ---------------------------------------------------------------
RENDER_TIMEOUT_S = 120
RENDER_QUALITY = "-ql"   # 480p15: fast, fine for metrics
MANIM_VERSION = "0.22.1"
FRAME_X = 7.11           # frame is x in [-7.11, 7.11], y in [-4, 4]
FRAME_Y = 4.0
