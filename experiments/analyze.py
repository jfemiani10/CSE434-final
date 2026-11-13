"""Turn JSONL attempt logs into metric tables.

    python experiments/analyze.py results/logs/<run_id> [more dirs or files ...]

Metric definitions are in CLAUDE.md. A "scene" is one (run, condition, model,
concept, scene_idx); its outcome is its last render attempt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from c2a.config import ROOT, TABLES_DIR
from c2a.logging_utils import read_logs

FIGURES_DIR = ROOT / "results" / "figures"
RATINGS_DIR = ROOT / "results" / "ratings"
TIERS = ["concrete", "structural", "abstract"]
# Categorical slots 1-2 from the validated dataviz palette (light mode, print).
CONDITION_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]

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


def attach_ratings(scenes: pd.DataFrame, run_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Add human correctness/clarity per scene (mean over raters; failed scene = 0)."""
    keys, ratings = [], []
    for rid in run_ids:
        k = RATINGS_DIR / f"{rid}_key.csv"
        if not k.exists():
            continue
        keys.append(pd.read_csv(k).assign(run_id=rid))
        for f in sorted(RATINGS_DIR.glob(f"{rid}_*.csv")):
            if f.name != k.name:
                ratings.append(pd.read_csv(f).assign(run_id=rid))
    if not keys or not ratings:
        return scenes, None
    key = pd.concat(keys)
    rat = pd.concat(ratings).dropna(subset=["correctness", "clarity"])
    per_video = rat.groupby(["run_id", "video_id"])[["correctness", "clarity"]].mean().reset_index()
    scene_scores = key.merge(per_video, on=["run_id", "video_id"], how="left")
    scenes = scenes.merge(scene_scores[["run_id", "condition", "concept_id", "scene_idx", "correctness", "clarity"]],
                          on=["run_id", "condition", "concept_id", "scene_idx"], how="left")
    scenes.loc[~scenes["success"], ["correctness", "clarity"]] = 0.0
    return scenes, rat


def rater_agreement(rat: pd.DataFrame) -> pd.DataFrame:
    """Per score: exact agreement, within-1 agreement, mean |diff|, Pearson r between the two raters."""
    raters = sorted(rat["rater"].unique())
    if len(raters) < 2:
        return pd.DataFrame()
    a, b = raters[:2]
    wide = rat.pivot_table(index=["run_id", "video_id"], columns="rater", values=["correctness", "clarity"])
    out = {}
    for m in ["correctness", "clarity"]:
        x, y = wide[(m, a)], wide[(m, b)]
        ok = x.notna() & y.notna()
        x, y = x[ok], y[ok]
        out[m] = {"videos": len(x), "exact": (x == y).mean(), "within_1": ((x - y).abs() <= 1).mean(),
                  "mean_abs_diff": (x - y).abs().mean(), "pearson_r": x.corr(y)}
    return pd.DataFrame(out).T.round(3)


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
    if "correctness" in scenes:
        out["human_correctness"] = g["correctness"].mean()
        out["human_clarity"] = g["clarity"].mean()
    return out.round(3)


def latex_rows(scenes: pd.DataFrame) -> str:
    """Rows for report Table 1: condition overall, then each tier."""
    def fmt(d: pd.DataFrame, label: str, repair: bool) -> str:
        n, ok = len(d), int(d["success"].sum())
        succ = d[d["success"]]
        reps = f"{succ['repairs'].mean():.2f}" if repair and len(succ) else "--"
        hum = [f"{d[c].mean():.2f}" if c in d and d[c].notna().all() else r"\tbd" for c in ("correctness", "clarity")]
        return (f"{label} & {100 * ok / n:.0f}\\% ({ok}/{n}) & {100 * d['first_try'].mean():.0f}\\% & "
                f"{reps} & {hum[0]} & {hum[1]} \\\\")
    lines = []
    for cond, d in scenes.groupby("condition", sort=False):
        repair = cond.endswith("repair") or "repair" in cond
        lines.append(fmt(d, f"\\texttt{{{cond.replace('_', chr(92) + '_')}}}", repair))
        for t in TIERS:
            dt = d[d["tier"] == t]
            if len(dt):
                lines.append(fmt(dt, f"\\quad {t} ({len(dt)})", repair))
        lines.append("\\addlinespace")
    return "\n".join(lines[:-1])


def plot_success_by_tier(scenes: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conds = list(dict.fromkeys(scenes["condition"]))
    groups = TIERS + ["all"]
    fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=200)
    width = 0.8 / len(conds)
    for i, cond in enumerate(conds):
        d = scenes[scenes["condition"] == cond]
        vals = [d[d["tier"] == t]["success"].mean() * 100 for t in TIERS] + [d["success"].mean() * 100]
        xs = [j + (i - (len(conds) - 1) / 2) * width for j in range(len(groups))]
        bars = ax.bar(xs, vals, width * 0.92, color=CONDITION_COLORS[i], label=cond.replace("_", " "))
        for x, v in zip(xs, vals):
            ax.text(x, v + 2, f"{v:.0f}%", ha="center", va="bottom", fontsize=7, color="#3d3d3a")
    ax.set_xticks(range(len(groups)), [g if g != "all" else "all scenes" for g in groups], fontsize=8)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"], fontsize=7, color="#6b6a65")
    ax.set_ylabel("Scenes rendered", fontsize=8, color="#3d3d3a")
    ax.yaxis.grid(True, color="#e8e7e2", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#bdbcb5")
    ax.tick_params(axis="both", length=0)
    ax.legend(frameon=False, fontsize=7, ncol=len(conds), loc="upper left", bbox_to_anchor=(0, 1.12))
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


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
    scenes, rat = attach_ratings(scenes, sorted(attempts["run_id"].unique()))
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

    if rat is not None:
        print("\n== Rater agreement ==")
        agree = rater_agreement(rat)
        print(agree if not agree.empty else f"(only one rater so far: {sorted(rat['rater'].unique())})")

    print("\n== LaTeX rows for report Table 1 ==")
    print(latex_rows(scenes))

    name = args.name or args.paths[0].stem
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plot_success_by_tier(scenes, FIGURES_DIR / f"{name}_success_by_tier.png")
    print(f"\nFigure: {(FIGURES_DIR / f'{name}_success_by_tier.png').relative_to(ROOT)}")
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    overall.to_csv(TABLES_DIR / f"{name}_overall.csv")
    by_tier.to_csv(TABLES_DIR / f"{name}_by_tier.csv")
    if not errors.empty:
        errors.to_csv(TABLES_DIR / f"{name}_errors.csv")
    scenes.to_csv(TABLES_DIR / f"{name}_scenes.csv", index=False)
    print(f"\nTables written to {TABLES_DIR}")


if __name__ == "__main__":
    main()
