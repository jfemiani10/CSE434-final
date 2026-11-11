"""Turn JSONL attempt logs into metric tables.

    python experiments/analyze.py results/logs/<run_id> [more dirs or files ...]

Metric definitions are in CLAUDE.md. A "scene" is one (run, condition, model,
concept, scene_idx); its outcome is its last render attempt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from c2a.config import TABLES_DIR
from c2a.logging_utils import read_logs

KEYS = ["run_id", "condition", "model", "concept_id", "tier", "scene_idx"]


def scene_table(attempts: pd.DataFrame) -> pd.DataFrame:
    r = attempts[attempts["phase"] == "render"].sort_values("attempt")
    g = r.groupby(KEYS, sort=False)
    scenes = g.agg(
        attempts=("attempt", "max"),
        success=("success", "last"),
        first_try=("success", "first"),
        final_error=("error_type", "last"),
        prompt_tokens=("prompt_tokens", "sum"),
        completion_tokens=("completion_tokens", "sum"),
        thinking_tokens=("thinking_tokens", "sum"),
        llm_latency_s=("latency_s", "sum"),
    ).reset_index()
    scenes["repairs"] = scenes["attempts"] - 1
    return scenes


def summarize(scenes: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = scenes.groupby(by)
    out = pd.DataFrame({
        "scenes": g.size(),
        "render_success": g["success"].mean(),
        "first_try_success": g["first_try"].mean(),
        # mean extra attempts, over successful scenes only (CLAUDE.md)
        "avg_repairs": scenes[scenes["success"]].groupby(by)["repairs"].mean(),
        "tokens_per_scene": g.apply(lambda d: (d.prompt_tokens + d.completion_tokens + d.thinking_tokens).mean(),
                                    include_groups=False),
    })
    return out.round(3)


def error_breakdown(attempts: pd.DataFrame) -> pd.DataFrame:
    failed = attempts[(attempts["phase"] == "render") & (~attempts["success"])]
    if failed.empty:
        return pd.DataFrame()
    return (failed.groupby(["condition", "model", "error_type"]).size()
            .unstack(fill_value=0))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--name", default=None, help="prefix for CSVs in results/tables/ (default: first path's name)")
    args = ap.parse_args()

    attempts = pd.DataFrame(read_logs(args.paths))
    if attempts.empty:
        print("No log rows found.")
        return
    scenes = scene_table(attempts)
    overall = summarize(scenes, ["condition", "model"])
    by_tier = summarize(scenes, ["condition", "model", "tier"])
    errors = error_breakdown(attempts)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(f"{len(attempts)} attempts, {len(scenes)} scenes, {scenes['concept_id'].nunique()} concepts\n")
    print("== By condition x model ==\n", overall, "\n", sep="")
    print("== By tier ==\n", by_tier, "\n", sep="")
    print("== Failed attempts by error type ==\n", errors if not errors.empty else "(none)", "\n", sep="")
    fails = scenes[~scenes["success"]]
    if not fails.empty:
        msgs = attempts[(~attempts["success"])][["concept_id", "scene_idx", "error_type", "error_msg"]]
        print("== Failure messages ==")
        for row in msgs.itertuples():
            print(f"  {row.concept_id} s{row.scene_idx} [{row.error_type}] {str(row.error_msg)[:140]}")

    name = args.name or args.paths[0].stem
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    overall.to_csv(TABLES_DIR / f"{name}_overall.csv")
    by_tier.to_csv(TABLES_DIR / f"{name}_by_tier.csv")
    if not errors.empty:
        errors.to_csv(TABLES_DIR / f"{name}_errors.csv")
    scenes.to_csv(TABLES_DIR / f"{name}_scenes.csv", index=False)
    print(f"\nTables written to {TABLES_DIR}")


if __name__ == "__main__":
    main()
