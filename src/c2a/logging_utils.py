"""JSONL experiment logger: one JSON object per line, one line per render attempt.

Each (run, condition, model, concept) job writes its own file, so parallel
worker processes never write to the same file. analyze.py reads them all.
Schema: see "Log schema" in CLAUDE.md. Append new fields, never rename.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class AttemptRecord:
    # --- core schema (CLAUDE.md) ---
    run_id: str
    concept_id: str
    tier: str
    condition: str
    model: str                 # provider model id, e.g. "gemini-3.5-flash"
    scene_idx: int             # 1-based, matches the class name Scene<idx>
    attempt: int               # 1-based
    phase: str                 # "render" | "layout"
    success: bool
    error_type: str | None
    error_msg: str | None
    layout_defects: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0     # LLM call latency
    code_path: str = ""
    timestamp: str = ""
    # --- appended fields ---
    model_key: str = ""        # short key from config.MODELS, e.g. "gemini"
    thinking_tokens: int = 0   # Gemini 3.x reasoning tokens (billed/rate-limited like output)
    llm_cached: bool = False   # response served from .cache/llm
    render_s: float = 0.0
    video_path: str | None = None
    scene_title: str = ""


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: AttemptRecord) -> None:
        if not record.timestamp:
            record.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")


def read_logs(paths: list[Path]) -> list[dict]:
    """Read every *.jsonl under the given files/directories."""
    rows: list[dict] = []
    for p in paths:
        files = sorted(p.rglob("*.jsonl")) if p.is_dir() else [p]
        for f in files:
            rows.extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())
    return rows
