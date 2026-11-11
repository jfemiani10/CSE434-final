"""Build a browsable HTML page for one run: per concept and scene, what went in and what came out.

    python experiments/review.py <run_id>          # writes outputs/<run_id>/review.html
    python experiments/review.py --list            # show available runs

For each concept: its description and storyboard. For each scene: pass/fail,
the error, the video, and collapsible panels with the exact prompt, the code
that was rendered, the model's raw reply and the error output.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from collections import defaultdict
from pathlib import Path

from c2a.config import CONDITIONS, LOGS_DIR, OUTPUTS_DIR, ROOT
from c2a.logging_utils import read_logs
from c2a.planner import get_concept

CSS = """
:root { --bg:#fff; --fg:#1c1c1c; --muted:#666; --card:#f6f6f4; --border:#ddd; --ok:#1a7f37; --bad:#c62828; --code:#f0f0ec; }
@media (prefers-color-scheme: dark) { :root { --bg:#161616; --fg:#e8e8e8; --muted:#9a9a9a; --card:#202020; --border:#333; --ok:#4cc26b; --bad:#ff6b6b; --code:#1b1b1b; } }
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; max-width:1100px; margin:0 auto; padding:24px 16px; }
h1 { margin:0 0 4px } h2 { margin-top:40px; border-bottom:1px solid var(--border); padding-bottom:4px }
.muted { color:var(--muted) } a { color:inherit }
table { border-collapse:collapse; width:100%; margin:12px 0 } td, th { text-align:left; padding:4px 8px; border-bottom:1px solid var(--border) }
.ok { color:var(--ok); font-weight:600 } .bad { color:var(--bad); font-weight:600 }
.scene { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin:12px 0 }
.scene h3 { margin:0 0 6px; font-size:16px }
video { width:100%; max-width:640px; border-radius:6px; background:#000; display:block; margin:8px 0 }
details { margin:6px 0 } summary { cursor:pointer; color:var(--muted) }
pre { background:var(--code); border:1px solid var(--border); border-radius:6px; padding:10px; overflow-x:auto; font-size:13px; white-space:pre-wrap; word-break:break-word }
.storyboard li { margin-bottom:6px }
.pill { display:inline-block; padding:0 8px; border-radius:10px; border:1px solid var(--border); font-size:12px; margin-left:6px }
"""


def esc(s: object) -> str:
    return html.escape("" if s is None else str(s))


def read_text(p: Path) -> str | None:
    return p.read_text() if p.exists() else None


def rel(target: Path, base: Path) -> str:
    return os.path.relpath(target, base)


def build(run_id: str) -> Path:
    log_dir = LOGS_DIR / run_id
    if not log_dir.exists():
        raise SystemExit(f"No logs at {log_dir}. Try --list.")
    out_root = OUTPUTS_DIR / run_id
    out_root.mkdir(parents=True, exist_ok=True)
    page = out_root / "review.html"
    rows = read_logs([log_dir])
    manifest = json.loads(read_text(log_dir / "manifest.json") or "{}")

    # job -> concept -> scene -> [attempts]
    tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        tree[(r["condition"], r.get("model_key") or r["model"])][r["concept_id"]][r["scene_idx"]].append(r)

    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Review {esc(run_id)}</title><style>{CSS}</style></head><body>",
             f"<h1>Run {esc(run_id)}</h1>"]
    if manifest:
        parts.append(f"<p class='muted'>Started {esc(manifest.get('started'))} · git {esc(manifest.get('git_commit'))} · "
                     f"models {esc(manifest.get('models'))} · args <code>{esc(' '.join(manifest.get('argv', [])))}</code></p>")

    # summary table
    parts.append("<table><tr><th>Concept</th><th>Tier</th><th>Condition / model</th><th>Scenes rendered</th></tr>")
    for (cond, model), concepts in sorted(tree.items()):
        for cid, scenes in sorted(concepts.items()):
            ok = sum(atts[-1]["success"] for atts in scenes.values())
            n_planned = _n_planned(cid)
            note = "" if len(scenes) == n_planned else f" <span class='muted'>({n_planned - len(scenes)} not run)</span>"
            tier = next(iter(scenes.values()))[0]["tier"]
            cls = "ok" if ok == n_planned else "bad"
            parts.append(f"<tr><td><a href='#{esc(cond)}-{esc(model)}-{esc(cid)}'>{esc(cid)}</a></td><td>{esc(tier)}</td>"
                         f"<td>{esc(cond)} / {esc(model)}</td><td class='{cls}'>{ok}/{n_planned}{note}</td></tr>")
    parts.append("</table>")

    for (cond, model), concepts in sorted(tree.items()):
        for cid, scenes in sorted(concepts.items()):
            parts.append(_concept_section(cid, cond, model, scenes, out_root, page.parent))

    parts.append("</body></html>")
    page.write_text("\n".join(parts))
    return page


def _n_planned(cid: str) -> int:
    from c2a.config import STORYBOARD_DIR
    p = STORYBOARD_DIR / f"{cid}.json"
    return len(json.loads(p.read_text())["storyboard"]["scenes"]) if p.exists() else 0


def _concept_section(cid, cond, model, scenes, out_root: Path, base: Path) -> str:
    from c2a.config import STORYBOARD_DIR
    concept = get_concept(cid)
    sb_path = STORYBOARD_DIR / f"{cid}.json"
    sb = json.loads(sb_path.read_text()) if sb_path.exists() else None
    s = [f"<h2 id='{esc(cond)}-{esc(model)}-{esc(cid)}'>{esc(concept['name'])}"
         f"<span class='pill'>{esc(concept['tier'])}</span><span class='pill'>{esc(cond)} / {esc(model)}</span></h2>",
         f"<p><b>Concept prompt:</b> {esc(concept['description'])}</p>"]
    if sb:
        s.append(f"<details><summary>Storyboard (planner: {esc(sb.get('planner_model'))}) "
                 f"<a href='{esc(rel(sb_path, base))}'>json</a></summary><ol class='storyboard'>")
        for sc in sb["storyboard"]["scenes"]:
            s.append(f"<li><b>{esc(sc['title'])}</b><br>{esc(sc['visual'])}<br><i class='muted'>“{esc(sc['narration'])}”</i></li>")
        s.append("</ol></details>")

    n = len(sb["storyboard"]["scenes"]) if sb else max(scenes)
    for idx in range(1, n + 1):
        atts = scenes.get(idx)
        if not atts:
            s.append(f"<div class='scene'><h3>Scene {idx}</h3><p class='muted'>Not run (job stopped before this scene).</p></div>")
            continue
        for a in atts:
            s.append(_attempt_card(a, base))
    return "\n".join(s)


def _attempt_card(a: dict, base: Path) -> str:
    code_path = ROOT / a["code_path"]
    stem = code_path.with_suffix("")  # .../scene_2_attempt_1
    prompt = read_text(stem.with_suffix(".prompt.md"))
    if prompt is None:
        prompt = _reconstruct_prompt(a)
    code = read_text(code_path)
    raw = read_text(stem.with_suffix(".raw.md"))
    stderr = read_text(stem.with_suffix(".stderr.txt"))
    status = ("<span class='ok'>RENDERED</span>" if a["success"]
              else f"<span class='bad'>FAILED · {esc(a['error_type'])}</span>")
    tokens = f"{a['prompt_tokens']} in / {a['completion_tokens']} out" + \
             (f" / {a['thinking_tokens']} thinking" if a.get("thinking_tokens") else "")
    c = [f"<div class='scene'><h3>Scene {a['scene_idx']}: {esc(a.get('scene_title'))} "
         f"<span class='muted'>· attempt {a['attempt']}</span> · {status}</h3>",
         f"<div class='muted'>{tokens} · LLM {a['latency_s']}s{' (cached)' if a.get('llm_cached') else ''}"
         f" · render {a.get('render_s', '?')}s</div>"]
    if a.get("error_msg"):
        c.append(f"<pre>{esc(a['error_msg'])}</pre>")
    if a.get("video_path"):
        c.append(f"<video controls preload='metadata' src='{esc(rel(ROOT / a['video_path'], base))}'></video>")
    for label, body, lang in [("Prompt sent to the model", prompt, ""), ("Code that was rendered", code, ""),
                              ("Raw model reply", raw, ""), ("Error output (last lines)", stderr, "")]:
        if body:
            c.append(f"<details><summary>{label}</summary><pre>{esc(body)}</pre></details>")
    c.append(f"<div class='muted'><a href='{esc(rel(code_path, base))}'>{esc(a['code_path'])}</a></div></div>")
    return "\n".join(c)


def _reconstruct_prompt(a: dict) -> str | None:
    """Older runs didn't save prompts; rebuild it (prompts are deterministic given the storyboard)."""
    try:
        from c2a.codegen import build_prompt
        from c2a.planner import get_storyboard
        concept = get_concept(a["concept_id"])
        prompt, system = build_prompt(concept, get_storyboard(concept), a["scene_idx"], CONDITIONS[a["condition"]])
        return f"(reconstructed: this run predates saved prompts)\n\n# SYSTEM\n\n{system}\n\n# PROMPT\n\n{prompt}"
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--list", action="store_true", help="list runs that have logs")
    args = ap.parse_args()
    if args.list or not args.run_id:
        for d in sorted(LOGS_DIR.iterdir()):
            if d.is_dir():
                print(d.name)
        return
    page = build(args.run_id)
    print(f"Wrote {page.relative_to(ROOT)}")
    if "WSL_DISTRO_NAME" in os.environ:
        print(f'Open in your Windows browser:  explorer.exe "$(wslpath -w {page})"')
    else:
        print(f"Open: file://{page}")


if __name__ == "__main__":
    main()
