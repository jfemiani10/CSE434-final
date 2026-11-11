"""Smoke test for an open model: ask it for one Manim scene, then render it.

Not part of the experiment (the prompt is inline and nothing is logged).
It only answers: is the model server up, how fast is it, and can it write
ManimCE code that renders?

    ollama serve            # in another terminal, if not already running
    python scripts/check_open_model.py                # qwen7b
    python scripts/check_open_model.py --model qwen3b
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

from openai import APIConnectionError, OpenAI

from c2a.config import MODELS, RENDER_TIMEOUT_S, SEED, TEMPERATURE

PROMPT = """Write a Manim Community Edition (v0.22, `from manim import *`) scene.
Class name: CheckScene (subclass of Scene).
Content: draw a right triangle with sides labeled a, b, c, then show the
equation a^2 + b^2 = c^2 below it using MathTex.
Keep everything inside the frame: x in [-7, 7], y in [-4, 4].
Return only one Python code block."""


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen7b", choices=[k for k, m in MODELS.items() if m.backend == "openai_compat"])
    args = ap.parse_args()
    spec = MODELS[args.model]

    client = OpenAI(base_url=spec.base_url, api_key="ollama")  # Ollama ignores the key
    print(f"Asking {spec.model_id} at {spec.base_url} ...")
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=spec.model_id,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=TEMPERATURE,
            seed=SEED,
        )
    except APIConnectionError:
        print(f"Can't reach {spec.base_url}. Is Ollama running? Try `ollama serve`, "
              f"then `ollama pull {spec.model_id}`.")
        return 1
    dt = time.time() - t0
    u = resp.usage
    print(f"{dt:.1f}s, {u.prompt_tokens} prompt + {u.completion_tokens} completion tokens "
          f"(~{u.completion_tokens / dt:.0f} tok/s overall)")

    out = Path("outputs/check_open_model") / args.model
    out.mkdir(parents=True, exist_ok=True)
    code_path = out / "check_scene.py"
    code_path.write_text(extract_code(resp.choices[0].message.content))
    print(f"Code saved to {code_path}")

    try:
        r = subprocess.run(
            [sys.executable, "-m", "manim", "-ql", "--media_dir", str(out / "media"),
             str(code_path), "CheckScene"],
            capture_output=True, text=True, timeout=RENDER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print("RENDER TIMEOUT")
        return 1
    if r.returncode == 0:
        videos = list((out / "media").rglob("CheckScene.mp4"))
        print(f"RENDER OK -> {videos[0] if videos else '(video path not found)'}")
        return 0
    print("RENDER FAILED. Last lines of the error:")
    print("\n".join(r.stderr.strip().splitlines()[-12:]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
