"""Render one generated scene in a subprocess and classify any failure.

LLM-written code never runs inside this Python process: Manim is launched as
a child process with a timeout, so a crash, infinite loop or `sys.exit` in the
generated code can't take the pipeline down with it.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from c2a.config import RENDER_TIMEOUT_S

STDERR_TAIL_LINES = 40


@dataclass
class RenderResult:
    success: bool
    video_path: str | None
    error_type: str | None   # see classify_error; None on success
    error_msg: str | None    # the single most useful line, e.g. "AttributeError: ..."
    stderr_tail: str         # last lines of output, for the repair prompt and debugging
    render_s: float


def render_scene(code_path: Path, scene_name: str, media_dir: Path,
                 timeout_s: int = RENDER_TIMEOUT_S, quality: str = "-ql") -> RenderResult:
    """Run `python -m manim <quality> code_path scene_name` and report what happened."""
    cmd = [sys.executable, "-m", "manim", quality, "--media_dir", str(media_dir),
           "--disable_caching", str(code_path), scene_name]
    # Wide COLUMNS stops Manim's rich tracebacks from wrapping (and truncating) error lines.
    env = {**os.environ, "COLUMNS": "400"}
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                              env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as e:
        out = _decode(e.stderr) + _decode(e.stdout)
        return RenderResult(False, None, "timeout", f"Render exceeded {timeout_s}s",
                            _tail(out), time.time() - t0)
    elapsed = time.time() - t0
    output = proc.stderr + "\n" + proc.stdout
    # The traceback is on stderr; stdout is progress logs that would push it out of the tail.
    error_text = proc.stderr if proc.stderr.strip() else proc.stdout

    if proc.returncode == 0:
        # Only accept a video written by *this* render. Manim also exits 0 when the
        # requested class doesn't exist (it renders whatever scene it finds instead),
        # so check the file name, not just the return code.
        videos = [p for p in media_dir.rglob(f"{scene_name}.mp4") if p.stat().st_mtime >= t0 - 1]
        if videos:
            return RenderResult(True, str(videos[0]), None, None, "", elapsed)
        if re.search(rf"Rendered (?!{re.escape(scene_name)}\b)\w+", output):
            msg = f"Scene class '{scene_name}' not found; Manim rendered a different class"
        else:
            msg = "Render produced no video (scene has no animations?)"
        return RenderResult(False, None, "other", msg, _tail(output), elapsed)

    error_type, error_msg = classify_error(error_text)
    return RenderResult(False, None, error_type, error_msg, _tail(error_text), elapsed)


# --- error classification ----------------------------------------------------

# An exception line: "NameError: name 'x' is not defined", or a bare "AssertionError".
_EXC_LINE = re.compile(r"^\s*[│|]?\s*(?:[\w.]+\.)?(\w+(?:Error|Exception))\s*(?::\s*(.*))?$", re.MULTILINE)


def classify_error(output: str) -> tuple[str, str]:
    """Map Manim's stderr to one of the taxonomy labels in CLAUDE.md.

    Returns (error_type, error_msg) where error_msg is the final exception line.
    Order matters: LaTeX failures surface as ValueError/RuntimeError, so they're
    checked before the generic exception-name rules.
    """
    exc_name, exc_msg = _last_exception(output)
    if exc_name:
        msg = f"{exc_name}: {exc_msg}" if exc_msg else f"{exc_name} (no message) in {_last_frame(output)}"
    else:
        msg = _last_nonempty_line(output)
    low = output.lower()

    if "latex error converting to dvi" in low or "latex compilation error" in low \
            or ("latex" in low and exc_name in {"ValueError", "RuntimeError", "LatexError"}):
        return "latex", msg
    if exc_name in {"SyntaxError", "IndentationError", "TabError"}:
        return "syntax", msg
    if exc_name in {"AttributeError", "NameError", "ImportError", "ModuleNotFoundError"}:
        return "hallucinated_api", msg
    if exc_name == "TypeError" and "__getattr__.<locals>.getter" in output:
        # Mobject.__getattr__ fakes any `get_*` attribute, so a nonexistent method like
        # Axes.get_graph(...) fails with a TypeError about argument count instead of
        # an AttributeError. It's still a hallucinated API.
        return "hallucinated_api", msg
    if exc_name == "TypeError":
        return "bad_signature", msg
    if "is not in the script" in low or "no scenes inside that module" in low:
        # Manim couldn't find the class we asked for: codegen didn't follow the naming rule.
        return "other", msg or "Scene class not found"
    return "other", msg


def _last_exception(output: str) -> tuple[str | None, str]:
    matches = list(_EXC_LINE.finditer(output))
    if not matches:
        return None, ""
    m = matches[-1]
    # Rich tracebacks wrap long messages and pad with box-drawing chars; tidy up.
    return m.group(1), (m.group(2) or "").strip().rstrip("│").strip()


def _last_frame(output: str) -> str:
    """Last 'path:line in func' location in a traceback, for errors with no message."""
    frames = re.findall(r"([\w./-]+\.py):(\d+) in (\w+)", output)
    if not frames:
        frames = [(f, n, fn) for f, n, fn in re.findall(r'File "([^"]+)", line (\d+), in (\w+)', output)]
    if not frames:
        return "unknown location"
    f, n, fn = frames[-1]
    return f"{fn} ({Path(f).name}:{n})"


def _last_nonempty_line(output: str) -> str:
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _tail(text: str, n: int = STDERR_TAIL_LINES) -> str:
    return "\n".join(text.rstrip().splitlines()[-n:])


def _decode(b: bytes | str | None) -> str:
    if b is None:
        return ""
    return b.decode(errors="replace") if isinstance(b, bytes) else b
