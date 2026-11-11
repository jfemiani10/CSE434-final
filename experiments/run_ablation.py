"""Run concepts x conditions x models and log every render attempt.

    python experiments/run_ablation.py --conditions zero_shot --models gemini --limit 12

Storyboards are planned first, one at a time (so parallel workers never plan
the same concept twice), then jobs run in a process pool. Rendering is
CPU-bound, so this uses processes, not threads.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from c2a.config import CONDITIONS, LOGS_DIR, MODELS, ROOT
from c2a.pipeline import new_run_id, run_concept
from c2a.planner import get_storyboard, load_concepts


def _job(args):
    concept_id, condition, model, run_id, use_cache = args
    try:
        o = run_concept(concept_id, condition, model, run_id, use_cache=use_cache)
        return concept_id, condition, model, o.n_success, len(o.scenes), None
    except Exception as e:  # keep the batch going; the failure is reported at the end
        return concept_id, condition, model, 0, 0, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conditions", nargs="+", default=["zero_shot"], choices=list(CONDITIONS))
    ap.add_argument("--models", nargs="+", default=["gemini"], choices=list(MODELS))
    ap.add_argument("--concepts", nargs="+", help="concept ids (default: all in data/concepts.json)")
    ap.add_argument("--tier", choices=["concrete", "structural", "abstract"])
    ap.add_argument("--midterm", action="store_true", help="only concepts marked midterm")
    ap.add_argument("--limit", type=int, help="first N concepts after filtering")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    concepts = load_concepts()
    if args.concepts:
        concepts = [c for c in concepts if c["id"] in set(args.concepts)]
    if args.tier:
        concepts = [c for c in concepts if c["tier"] == args.tier]
    if args.midterm:
        concepts = [c for c in concepts if c.get("midterm")]
    concepts = concepts[: args.limit]
    if not concepts:
        print("No concepts selected.")
        return 1

    run_id = args.run_id or new_run_id()
    run_dir = LOGS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "argv": sys.argv[1:], "git_commit": _git_commit(),
        "conditions": args.conditions, "models": {k: MODELS[k].model_id for k in args.models},
        "concepts": [c["id"] for c in concepts], "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2) + "\n")
    print(f"run_id={run_id}: {len(concepts)} concepts x {len(args.conditions)} conditions "
          f"x {len(args.models)} models", flush=True)

    for c in concepts:
        sb = get_storyboard(c)
        print(f"  storyboard {c['id']}: {len(sb.scenes)} scenes", flush=True)

    jobs = [(c["id"], cond, m, run_id, not args.no_cache)
            for c in concepts for cond in args.conditions for m in args.models]
    t0 = time.time()
    failures = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_job, j) for j in jobs]
        for i, f in enumerate(as_completed(futures), 1):
            cid, cond, m, ok, n, err = f.result()
            status = f"ERROR {err}" if err else f"{ok}/{n} scenes"
            print(f"[{i}/{len(jobs)}] {cid} {cond} {m}: {status}", flush=True)
            if err:
                failures.append((cid, cond, m, err))

    print(f"\nDone in {time.time() - t0:.0f}s. Logs: {run_dir.relative_to(ROOT)}")
    print(f"Metrics:  python experiments/analyze.py {run_dir.relative_to(ROOT)}")
    print(f"Browse:   python experiments/review.py {run_id}")
    if failures:
        print(f"{len(failures)} job(s) crashed (not render failures; pipeline errors):")
        for f in failures:
            print("  ", *f)
    return 1 if failures else 0


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, cwd=ROOT).stdout.strip() or None
    except OSError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
