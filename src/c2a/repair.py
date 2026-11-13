"""Stage 3 repair: failed code + its error -> corrected code.

The repair prompt is stateless: it carries the original task, the code that
failed and the error, so each attempt is one cacheable LLM call. On attempt k
the model sees only the most recent code and error, not the full history,
which keeps prompts short and mirrors how a person would fix a crash.
"""
from __future__ import annotations

from c2a.codegen import GeneratedCode, enforce_class_name, extract_code, scene_class_name
from c2a.config import MANIM_VERSION
from c2a.llm import LLM
from c2a.prompting import render_prompt
from c2a.render import RenderResult


def repair_scene_code(llm: LLM, prev: GeneratedCode, result: RenderResult, scene_idx: int,
                      attempt: int) -> GeneratedCode:
    """Ask the model to fix `prev` given the render failure. `attempt` is the attempt that failed."""
    class_name = scene_class_name(scene_idx)
    prompt = render_prompt(
        "repair",
        original_prompt=prev.prompt,
        attempt=attempt, code=prev.code.rstrip(), error_msg=result.error_msg or result.error_type,
        error_tail=result.stderr_tail.strip() or "(no output)",
        manim_version=MANIM_VERSION, class_name=class_name,
    )
    resp = llm.generate(prompt, system=prev.system)
    code = extract_code(resp.text)
    code, renamed_from = enforce_class_name(code, class_name)
    # Keep the *original* task prompt on the object so later repairs don't nest prompts.
    return GeneratedCode(code, class_name, resp, renamed_from,
                         prompt=prev.prompt, system=prev.system, sent_prompt=prompt)

