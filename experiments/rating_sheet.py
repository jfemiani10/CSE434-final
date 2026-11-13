"""Make a blind human-rating packet for a run.

    python experiments/rating_sheet.py <run_id>

Writes outputs/<run_id>/rating/ (self-contained, zip it to share):
  rate.html        shuffled videos labeled V01, V02, ... with no condition shown,
                   score boxes for correctness and clarity (1-5), and a button that
                   downloads the rater's scores as a CSV
  videos/Vnn.mp4   the videos
and results/ratings/<run_id>_key.csv, which maps each video id back to every
(condition, concept, scene) that produced it. Identical code renders identical
video, so a scene that rendered on the first try in two conditions is rated once.

Raters save their CSV as results/ratings/<run_id>_<rater>.csv. analyze.py
--ratings joins them back; failed scenes score 0.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import random
import shutil
from collections import defaultdict
from pathlib import Path

from c2a.config import LOGS_DIR, OUTPUTS_DIR, ROOT
from c2a.logging_utils import read_logs
from c2a.planner import get_concept, get_storyboard

RATINGS_DIR = ROOT / "results" / "ratings"


def final_attempts(rows: list[dict]) -> dict[tuple, dict]:
    """(condition, concept, scene) -> last render attempt."""
    last: dict[tuple, dict] = {}
    for r in sorted(rows, key=lambda r: r["attempt"]):
        if r["phase"] == "render":
            last[(r["condition"], r["concept_id"], r["scene_idx"])] = r
    return last


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id")
    ap.add_argument("--seed", type=int, default=434)
    args = ap.parse_args()

    rows = read_logs([LOGS_DIR / args.run_id])
    finals = final_attempts(rows)

    # Group rendered scenes by the exact code that produced them.
    by_code: dict[str, list[dict]] = defaultdict(list)
    for r in finals.values():
        if r["success"] and r.get("video_path"):
            digest = hashlib.sha256((ROOT / r["code_path"]).read_bytes()).hexdigest()
            by_code[digest].append(r)

    groups = sorted(by_code.values(), key=lambda g: (g[0]["concept_id"], g[0]["scene_idx"], g[0]["condition"]))
    random.Random(args.seed).shuffle(groups)

    out = OUTPUTS_DIR / args.run_id / "rating"
    if out.exists():
        shutil.rmtree(out)
    (out / "videos").mkdir(parents=True)
    RATINGS_DIR.mkdir(parents=True, exist_ok=True)

    key_rows, cards = [], []
    for i, g in enumerate(groups, 1):
        vid = f"V{i:02d}"
        first = g[0]
        shutil.copy(ROOT / first["video_path"], out / "videos" / f"{vid}.mp4")
        for r in g:
            key_rows.append({"video_id": vid, "condition": r["condition"], "concept_id": r["concept_id"],
                             "tier": r["tier"], "scene_idx": r["scene_idx"], "attempt": r["attempt"]})
        concept = get_concept(first["concept_id"])
        scene = get_storyboard(concept).scenes[first["scene_idx"] - 1]
        cards.append(_card(vid, concept["name"], scene.title, scene.visual, scene.narration))

    with (RATINGS_DIR / f"{args.run_id}_key.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(key_rows[0]))
        w.writeheader()
        w.writerows(key_rows)

    (out / "rate.html").write_text(_page(args.run_id, cards, [f"V{i:02d}" for i in range(1, len(groups) + 1)]))
    print(f"{len(groups)} distinct videos to rate (from {sum(len(g) for g in groups)} rendered scenes)")
    print(f"Packet: {(out).relative_to(ROOT)}/  (zip and share: cd {out.parent} && zip -r rating.zip rating)")
    print(f"Key:    {(RATINGS_DIR / f'{args.run_id}_key.csv').relative_to(ROOT)}")
    print(f"Raters save their CSV to results/ratings/{args.run_id}_<name>.csv")


def _card(vid, concept, title, visual, narration) -> str:
    e = html.escape
    return f"""<section class="card" id="{vid}">
<h2>{vid} <span class="muted">· {e(concept)}: {e(title)}</span></h2>
<video controls preload="metadata" src="videos/{vid}.mp4"></video>
<details><summary>What this scene was supposed to show</summary>
<p>{e(visual)}</p><p class="muted"><i>Narration: “{e(narration)}”</i></p></details>
<div class="scores">
<label>Correctness <select data-v="{vid}" data-k="correctness">{_opts()}</select></label>
<label>Clarity <select data-v="{vid}" data-k="clarity">{_opts()}</select></label>
<label class="notes">Notes <input data-v="{vid}" data-k="notes" type="text"></label>
</div></section>"""


def _opts() -> str:
    return '<option value="">–</option>' + "".join(f'<option>{i}</option>' for i in range(1, 6))


def _page(run_id: str, cards: list[str], ids: list[str]) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Rate videos</title>
<style>
:root {{ --bg:#fff; --fg:#1c1c1c; --muted:#666; --card:#f6f6f4; --border:#ddd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --fg:#e8e8e8; --muted:#9a9a9a; --card:#202020; --border:#333; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,sans-serif; max-width:900px; margin:0 auto; padding:24px 16px; }}
.muted {{ color:var(--muted); font-weight:normal }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin:16px 0 }}
h2 {{ font-size:17px; margin:0 0 8px }}
video {{ width:100%; border-radius:6px; background:#000 }}
.scores {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:8px; align-items:center }}
.notes {{ flex:1; min-width:200px; display:flex; gap:6px }} .notes input {{ flex:1 }}
select, input, button {{ font:inherit; padding:2px 6px }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--border); display:flex; gap:12px; align-items:center; flex-wrap:wrap }}
</style></head><body>
<h1>Rate the videos</h1>
<p>Score each clip 1–5. <b>Correctness:</b> is the math or CS shown right? (1 = wrong or misleading, 5 = fully correct.)
<b>Clarity:</b> is it easy to follow and visually clean? Overlaps, off-screen objects and clutter lower it. (1 = confusing or messy, 5 = clean and clear.)
Rate what you see, not the code. You can expand “What this scene was supposed to show” for context. Your choices are saved in this browser as you go.</p>
<div class="bar"><label>Your name <input id="rater" type="text" placeholder="jonah or koray"></label>
<button id="dl">Download my scores (CSV)</button><span id="count" class="muted"></span></div>
{''.join(cards)}
<script>
const IDS = {ids!r};
const KEY = "ratings-{run_id}";
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
const fields = document.querySelectorAll("[data-v]");
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} count(); }}
function count() {{
  const done = IDS.filter(v => state[v] && state[v].correctness && state[v].clarity).length;
  document.getElementById("count").textContent = done + " / " + IDS.length + " rated";
}}
fields.forEach(el => {{
  const v = el.dataset.v, k = el.dataset.k;
  if (state[v] && state[v][k]) el.value = state[v][k];
  el.addEventListener("input", () => {{ state[v] = state[v] || {{}}; state[v][k] = el.value; save(); }});
}});
const rater = document.getElementById("rater");
try {{ rater.value = localStorage.getItem(KEY + "-rater") || ""; }} catch (e) {{}}
rater.addEventListener("input", () => {{ try {{ localStorage.setItem(KEY + "-rater", rater.value); }} catch (e) {{}} }});
document.getElementById("dl").addEventListener("click", () => {{
  const name = (rater.value || "rater").trim().toLowerCase().replace(/[^a-z0-9_-]/g, "");
  const q = s => '"' + String(s || "").replace(/"/g, '""') + '"';
  const lines = ["video_id,rater,correctness,clarity,notes"].concat(
    IDS.map(v => [v, name, (state[v]||{{}}).correctness || "", (state[v]||{{}}).clarity || "", q((state[v]||{{}}).notes)].join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\\n") + "\\n"], {{type: "text/csv"}}));
  a.download = "{run_id}_" + name + ".csv"; a.click();
}});
count();
</script></body></html>"""


if __name__ == "__main__":
    main()
