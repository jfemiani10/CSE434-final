"""Stage 1: concept -> storyboard (a validated list of scenes).

Storyboards are cached in data/storyboards/<concept_id>.json and committed, so
every condition and every codegen model sees the identical plan for a concept.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

from c2a.config import CONCEPTS_PATH, PLANNER_MODEL, STORYBOARD_DIR
from c2a.llm import LLM
from c2a.prompting import render_prompt


class SceneSpec(BaseModel):
    title: str = Field(min_length=1)
    visual: str = Field(min_length=10)
    narration: str = Field(min_length=1)


class Storyboard(BaseModel):
    scenes: list[SceneSpec] = Field(min_length=2, max_length=6)


def load_concepts() -> list[dict]:
    return json.loads(CONCEPTS_PATH.read_text())


def get_concept(concept_id: str) -> dict:
    for c in load_concepts():
        if c["id"] == concept_id:
            return c
    raise KeyError(f"No concept {concept_id!r} in {CONCEPTS_PATH}")


def get_storyboard(concept: dict, regenerate: bool = False) -> Storyboard:
    """Return the cached storyboard for a concept, planning it first if needed."""
    path = STORYBOARD_DIR / f"{concept['id']}.json"
    if path.exists() and not regenerate:
        return Storyboard.model_validate(json.loads(path.read_text())["storyboard"])

    llm = LLM(PLANNER_MODEL)
    prompt = render_prompt("planner", name=concept["name"], description=concept["description"])
    system = render_prompt("planner_system")
    last_err: Exception | None = None
    for _ in range(2):  # one retry if the JSON doesn't validate
        resp = llm.generate(prompt, system=system, json_schema=Storyboard)
        try:
            sb = Storyboard.model_validate_json(resp.text)
            break
        except ValidationError as e:
            last_err = e
            # Change the prompt slightly so the retry isn't served from the cache.
            prompt += "\n\n(Return valid JSON matching the schema.)"
    else:
        raise RuntimeError(f"Planner output for {concept['id']} failed validation: {last_err}")

    STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "concept_id": concept["id"],
        "planner_model": resp.model_id,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "thinking_tokens": resp.thinking_tokens,
        "storyboard": sb.model_dump(),
    }, indent=2) + "\n")
    return sb
