"""Load prompt templates from src/c2a/prompts/ and fill in $placeholders."""
from __future__ import annotations

from string import Template

from c2a.config import PROMPTS_DIR


def render_prompt(template: str, /, **values) -> str:
    """`render_prompt("planner", name=...)` reads prompts/planner.md and substitutes.

    Uses string.Template ($var) rather than str.format ({var}) so that literal
    braces in prompts (JSON, Python dicts, LaTeX) need no escaping.
    Raises KeyError if a placeholder is left unfilled.
    """
    text = (PROMPTS_DIR / f"{template}.md").read_text()
    return Template(text).substitute(**values).strip()
