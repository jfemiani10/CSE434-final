"""End to end for one (concept, condition, model): storyboard -> code -> render -> video.

    python -m c2a.pipeline --concept pythagorean_theorem --condition zero_shot --model gemini

Outputs go to outputs/<run_id>/<condition>__<model>/<concept_id>/ and the
per-attempt log to results/logs/<run_id>/<condition>__<model>__<concept_id>.jsonl.
"""
from __future__ import annotations

import argparse
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from c2a.codegen import generate_scene_code
from c2a.config import (CONDITIONS, IMPLEMENTED_CONDITIONS, LOGS_DIR, MODELS, OUTPUTS_DIR,
                        RENDER_QUALITY, ROOT)
from c2a.llm import LLM
from c2a.logging_utils import AttemptRecord, JsonlLogger
from c2a.planner import get_concept, get_storyboard
from c2a.render import render_scene


@dataclass
class SceneOutcome:
    scene_idx: int
    success: bool
    attempts: int
    error_type: str | None
    video_path: str | None


@dataclass
class ConceptOutcome:
    concept_id: str
    condition: str
    model_key: str
    scenes: list[SceneOutcome] = field(default_factory=list)
    final_video: str | None = None

    @property
    def n_success(self) -> int:
        return sum(s.success for s in self.scenes)


def new_run_id() -> str:
    return f"{datetime.now():%Y-%m-%d_%H%M}_{secrets.token_hex(2)}"


def run_concept(concept_id: str, condition_key: str, model_key: str, run_id: str,
                use_cache: bool = True) -> ConceptOutcome:
    if condition_key not in IMPLEMENTED_CONDITIONS:
        raise NotImplementedError(f"Condition {condition_key!r} isn't built yet "
                                  f"(implemented: {sorted(IMPLEMENTED_CONDITIONS)})")
    condition = CONDITIONS[condition_key]
    concept = get_concept(concept_id)
    sb = get_storyboard(concept)
    llm = LLM(model_key, use_cache=use_cache)

    job = f"{condition_key}__{model_key}"
    out_dir = OUTPUTS_DIR / run_id / job / concept_id
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = JsonlLogger(LOGS_DIR / run_id / f"{job}__{concept_id}.jsonl")
    outcome = ConceptOutcome(concept_id, condition_key, model_key)

    for scene_idx in range(1, len(sb.scenes) + 1):
        # Zero-shot: exactly one attempt. The repair loop (Phase 2) will wrap this.
        attempt = 1
        gen = generate_scene_code(llm, concept, sb, scene_idx, condition)
        code_path = out_dir / f"scene_{scene_idx}_attempt_{attempt}.py"
        code_path.write_text(gen.code)
        (out_dir / f"scene_{scene_idx}_attempt_{attempt}.prompt.md").write_text(
            f"# SYSTEM\n\n{gen.system}\n\n# PROMPT\n\n{gen.prompt}\n")
        (out_dir / f"scene_{scene_idx}_attempt_{attempt}.raw.md").write_text(gen.response.text)

        result = render_scene(code_path, gen.class_name,
                              out_dir / "media" / f"scene_{scene_idx}_attempt_{attempt}",
                              quality=RENDER_QUALITY)
        if not result.success:
            (out_dir / f"scene_{scene_idx}_attempt_{attempt}.stderr.txt").write_text(result.stderr_tail)

        r = gen.response
        logger.log(AttemptRecord(
            run_id=run_id, concept_id=concept_id, tier=concept["tier"], condition=condition_key,
            model=r.model_id, scene_idx=scene_idx, attempt=attempt, phase="render",
            success=result.success, error_type=result.error_type, error_msg=result.error_msg,
            prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
            latency_s=round(r.latency_s, 2), code_path=_rel(code_path),
            model_key=model_key, thinking_tokens=r.thinking_tokens, llm_cached=r.cached,
            render_s=round(result.render_s, 2),
            video_path=_rel(Path(result.video_path)) if result.video_path else None,
            scene_title=sb.scenes[scene_idx - 1].title,
            model_version=r.model_version,
        ))
        outcome.scenes.append(SceneOutcome(scene_idx, result.success, attempt,
                                           result.error_type, result.video_path))

    videos = [Path(s.video_path) for s in outcome.scenes if s.success and s.video_path]
    if videos:
        outcome.final_video = stitch_videos(videos, out_dir / f"{concept_id}.mp4")
    return outcome


def stitch_videos(videos: list[Path], dest: Path) -> str | None:
    """Concatenate scene videos with ffmpeg (demo only; metrics are per scene)."""
    listing = dest.with_suffix(".txt")
    listing.write_text("".join(f"file '{v.resolve()}'\n" for v in videos))
    proc = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(dest)],
        capture_output=True, text=True)
    return str(dest) if proc.returncode == 0 else None


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--concept", required=True)
    ap.add_argument("--condition", default="zero_shot", choices=list(CONDITIONS))
    ap.add_argument("--model", default="gemini", choices=list(MODELS))
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--no-cache", action="store_true", help="always call the LLM, ignore cached responses")
    args = ap.parse_args()

    run_id = args.run_id or new_run_id()
    o = run_concept(args.concept, args.condition, args.model, run_id, use_cache=not args.no_cache)
    print(f"run_id={run_id}  {o.concept_id} [{o.condition} / {o.model_key}]: "
          f"{o.n_success}/{len(o.scenes)} scenes rendered")
    for s in o.scenes:
        print(f"  scene {s.scene_idx}: {'OK' if s.success else 'FAIL ' + str(s.error_type)}")
    if o.final_video:
        print(f"video: {o.final_video}")


if __name__ == "__main__":
    main()
