"""Stage 2: one storyboard scene -> ManimCE code.

Post-processing is kept minimal on purpose (it's part of every condition, so it
shouldn't quietly fix the errors we're trying to measure):
  1. pull the code out of the markdown fence, and
  2. rename the Scene subclass to the name the renderer will ask for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from c2a.config import FRAME_X, FRAME_Y, MANIM_VERSION, Condition
from c2a.llm import LLM, LLMResponse
from c2a.planner import Storyboard
from c2a.prompting import render_prompt

_FENCE = re.compile(r"```[ \t]*([\w+-]*)[ \t]*\n(.*?)```", re.DOTALL)
_SCENE_CLASS = re.compile(r"^class\s+(\w+)\s*\(\s*([\w.]*Scene)\s*\)\s*:", re.MULTILINE)


@dataclass
class GeneratedCode:
    code: str
    class_name: str
    response: LLMResponse
    renamed_from: str | None   # original class name if we had to rename it


def scene_class_name(scene_idx: int) -> str:
    return f"Scene{scene_idx}"


def storyboard_outline(sb: Storyboard) -> str:
    return "\n".join(f"{i}. {s.title}: {s.visual}" for i, s in enumerate(sb.scenes, start=1))


def build_prompt(concept: dict, sb: Storyboard, scene_idx: int, condition: Condition) -> tuple[str, str]:
    if condition.few_shot or condition.rag:
        raise NotImplementedError("few-shot / RAG prompts arrive in Phases 3-4")
    scene = sb.scenes[scene_idx - 1]
    prompt = render_prompt(
        "codegen_zero_shot",
        concept_name=concept["name"], storyboard_outline=storyboard_outline(sb),
        scene_idx=scene_idx, title=scene.title, visual=scene.visual, narration=scene.narration,
        class_name=scene_class_name(scene_idx), frame_x=FRAME_X, frame_y=f"{FRAME_Y:g}",
    )
    system = render_prompt("codegen_system", manim_version=MANIM_VERSION)
    return prompt, system


def generate_scene_code(llm: LLM, concept: dict, sb: Storyboard, scene_idx: int,
                        condition: Condition) -> GeneratedCode:
    prompt, system = build_prompt(concept, sb, scene_idx, condition)
    resp = llm.generate(prompt, system=system)
    code = extract_code(resp.text)
    code, renamed_from = enforce_class_name(code, scene_class_name(scene_idx))
    return GeneratedCode(code, scene_class_name(scene_idx), resp, renamed_from)


def extract_code(text: str) -> str:
    """Return the longest Python code block, or the whole text if there's no fence.

    Every fence (```bash, ```text, ...) must be matched, not just Python ones;
    otherwise a closing fence gets mistaken for an opening one.
    """
    blocks = _FENCE.findall(text)  # [(lang, body), ...]
    python = [body for lang, body in blocks if lang.lower() in {"python", "py", ""}]
    candidates = python or [body for _, body in blocks]
    code = max(candidates, key=len) if candidates else text
    return code.strip() + "\n"


def enforce_class_name(code: str, wanted: str) -> tuple[str, str | None]:
    """Rename the first Scene subclass to `wanted`. Returns (code, old_name or None)."""
    m = _SCENE_CLASS.search(code)
    if not m or m.group(1) == wanted:
        return code, None
    old = m.group(1)
    # Replace whole-word uses too (e.g. super(OldName, self)).
    return re.sub(rf"\b{re.escape(old)}\b", wanted, code), old
