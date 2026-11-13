# CLAUDE.md — Concept-to-Animation

Project context for Claude Code. Read this before making changes. The working task list lives in `TODO.md`.

## What this project is

CSE 434 (Generative AI, Dr. Yang Zhang, Miami University, Fall 2026) final project by **Jonah Femiani** and **Koray Bayram**.

The system takes a short text description of a math/CS concept (e.g. "binary search", "the Pythagorean theorem") and generates a **narrated Manim Community Edition (ManimCE) explainer video**, in the style of 3Blue1Brown.

**Research question:** Which generative techniques make LLM-written animation code render reliably and produce clear, uncluttered visuals? The main failure modes are:
1. Hallucinated or outdated Manim APIs (code crashes)
2. Bad layout (objects overlap or leave the frame)

This is a **research project, not just a demo**. The deliverable is the ablation results table. Every pipeline run must be logged so it can be measured.

## Pipeline

```
concept ──► [1 Planner] ──► storyboard (JSON: scenes[{title, visual, narration}])
                │
                ▼  for each scene
          [2 Code generator] ──► ManimCE code (one Scene subclass)
                │        ▲
                ▼        │ traceback (≤ N retries)
          [3 Render] ────┘  render-and-repair loop
                │        ▲
                ▼        │ defect list (≤ M retries)
          [4 Layout check] ┘  overlap / off-frame repair
                │
                ▼
          [5 Narration] manim-voiceover (TTS) ──► stitched final .mp4
```

Optional augmentations to stage 2:
- **Few-shot:** hand-picked example scenes from the Manim docs in the prompt
- **RAG:** retrieve relevant Manim docs/examples for the scene, inject into the prompt

## Experiment design (the ablation)

This is a **cumulative (additive) ablation**: start from a bare zero-shot baseline and add one technique per condition, so the jump between adjacent rows is that technique's contribution *given everything above it*. (A classic leave-one-out ablation would instead start from the full pipeline and remove one part at a time; if budget allows, add `full_minus_rag` / `full_minus_fewshot` rows to check that the order of stacking isn't driving the conclusions.)

Conditions, each run on every concept. `zero_shot_repair` is an extra row, built second and used for the midterm (baseline vs. one improvement). It also isolates repair's effect without few-shot/RAG:

| Condition id        | Few-shot | RAG | Error repair | Layout repair |
|---------------------|:-------:|:---:|:------------:|:-------------:|
| `zero_shot`         |         |     |              |               |
| `zero_shot_repair`  |         |     | ✓            |               |
| `few_shot`          | ✓       |     |              |               |
| `rag`               | ✓       | ✓   |              |               |
| `rag_repair`        | ✓       | ✓   | ✓            |               |
| `rag_repair_layout` | ✓       | ✓   | ✓            | ✓             |

**Models (revised 2026-11-13; Dr. Zhang approved swapping models from the proposal):**
- **Planner and codegen:** `gemini-3.5-flash` (`thinking_level=low`) via the Gemini API. Qwen2.5-Coder was tried and dropped because its output quality was too poor.
- **Rate limits:** the free tier allows **20 requests/day per model**, which can't cover even the midterm (zero-shot + repair on 6 concepts is about 40–60 calls). Use a **paid (billing-enabled) key**. Keep response caching on so reruns cost nothing.
- `qwen7b`, `qwen3b` (Qwen2.5-Coder, 4-bit via Ollama; 4-bit is approved if used) and `llama2` remain registered in `config.py` as optional extra models. They are not part of the main experiment.
- Changes from the proposal are allowed as long as they aren't too large. LangChain is not expected.

**Ollama (only if a local model is used):** OpenAI-compatible API at `localhost:11434/v1`. **Gotcha:** Ollama's default context window is small and it **silently truncates** longer prompts. Set `OLLAMA_CONTEXT_LENGTH=8192` (see README). Smoke test: `python scripts/check_open_model.py --model qwen7b`.

Keep every model behind the `LLM` interface (`llm.py`) so models can be swapped. API backends get response caching and retry with backoff.

**Fairness rules:**
- For a given concept, use the **same storyboard** (planner output) across all conditions so only codegen differs. Cache storyboards in `data/storyboards/`.
- **All storyboards come from one planner model:** `gemini-3.5-flash` (`PLANNER_MODEL` in `config.py`; each storyboard JSON records `planner_model`). All 6 were made 2026-11-10. If any are regenerated, regenerate all 6 together.
- **Model drift note:** Google counted our `gemini-3.5-flash` requests against a quota for `gemini-3.6-flash`, so the 3.5 name may be an alias for a newer model that can change over time. All 6 storyboards were made in one batch on 2026-11-10, so they're consistent with each other. Logs record `model_version` from the API, so mention the alias in the report and check that codegen runs report the same version.
- Fixed temperature (default 0.2) and seed where supported.
- Conditions without repair get exactly 1 render attempt.

## Metrics (definitions — keep consistent)

All metrics are computed per scene, then aggregated by condition × model × tier.

- **Render success rate:** fraction of scenes that render without error within the attempt budget.
- **First-try success rate:** fraction that render on attempt 1.
- **Avg repair iterations:** mean number of extra attempts, computed over successful scenes only.
- **Layout-defect rate:** fraction of *rendered* scenes with ≥1 overlap or off-frame defect, measured at the final attempt.
- **Error taxonomy** (for failed attempts): `hallucinated_api` (AttributeError/NameError/ImportError on a Manim name), `bad_signature` (TypeError), `latex` (LaTeX compile errors), `timeout`, `syntax`, `other`.
- **Human ratings (1–5):** mathematical correctness and visual clarity, on a sample of final videos, recorded in `results/human_ratings.csv`.

## Dataset

- `data/concepts.json`: **6** team-curated concepts, 2 per tier, 20 storyboard scenes in total. This is the whole project's set (the proposal said 40; cut to 12, then to 6 on 2026-11-13):
  - `concrete`: Pythagorean theorem, derivative as slope
  - `structural`: matrix multiplication, binary search
  - `abstract`: recursion, Big-O notation
  - Schema: `{"id": "binary_search", "name": "Binary search", "tier": "structural", "description": "one-sentence prompt"}`
- `data/fewshot/`: curated example scenes (`.py`), from Manim Community docs/examples.
- `data/manim_docs/`: the RAG corpus (ManimCE docs + example gallery), chunked and indexed.

## Repo layout (target)

```
.
├── CLAUDE.md
├── TODO.md
├── pyproject.toml / requirements.txt
├── .env.example              # GEMINI_API_KEY, HF_TOKEN
├── data/
│   ├── concepts.json
│   ├── storyboards/          # cached planner outputs, one JSON per concept
│   ├── fewshot/
│   └── manim_docs/           # raw docs + built index
├── src/c2a/
│   ├── config.py             # condition definitions, model names, budgets
│   ├── llm.py                # unified client: Gemini (+ optional Ollama/OpenAI-compatible)
│   ├── prompts/              # prompt templates as .md/.txt, not inline strings
│   ├── planner.py
│   ├── codegen.py
│   ├── rag.py
│   ├── render.py             # subprocess Manim render + error classification
│   ├── layout.py             # bounding-box overlap / off-frame checker
│   ├── repair.py             # render-and-repair + layout-repair loops
│   ├── narration.py          # manim-voiceover integration
│   ├── logging_utils.py      # JSONL experiment logger
│   └── pipeline.py           # end-to-end: concept -> video
├── experiments/
│   ├── run_ablation.py       # concepts × conditions × models
│   └── analyze.py            # logs -> tables + figures
├── results/
│   ├── logs/                 # *.jsonl, one line per render attempt
│   ├── tables/
│   ├── figures/
│   └── human_ratings.csv
├── outputs/<run_id>/<condition>__<model>/<concept_id>/   # generated code, raw LLM replies, stderr, mp4s (gitignored)
├── app/                      # demo: type a concept, get a video
├── report/                   # midterm + final report sources
└── tests/
```

## Commands

```bash
# render a scene by hand (always use -ql for experiments: 480p15, fast)
manim -ql path/to/scene.py SceneName

# run the full pipeline on one concept
python -m c2a.pipeline --concept binary_search --condition zero_shot --model gemini

# run the ablation (use --limit or --concepts for quick checks)
python experiments/run_ablation.py --conditions zero_shot zero_shot_repair --models gemini

# build tables from one or more runs' logs
python experiments/analyze.py results/logs/<run_id>

pytest
```

## Log schema (one JSON line per render attempt)

```json
{
  "run_id": "2026-11-12_a1b2",
  "concept_id": "binary_search",
  "tier": "structural",
  "condition": "rag_repair",
  "model": "gemini-flash",
  "scene_idx": 2,
  "attempt": 1,
  "phase": "render | layout",
  "success": false,
  "error_type": "hallucinated_api",
  "error_msg": "AttributeError: 'Axes' object has no attribute 'get_graph'",
  "layout_defects": [{"type": "overlap", "a": "MathTex#3", "b": "Arrow#5", "iou": 0.31}],
  "prompt_tokens": 1834,
  "completion_tokens": 612,
  "latency_s": 7.4,
  "code_path": "outputs/2026-11-12_a1b2/zero_shot__gemini/binary_search/scene_2_attempt_1.py",
  "timestamp": "2026-11-12T19:03:11Z"
}
```

Logs live in `results/logs/<run_id>/<condition>__<model>__<concept>.jsonl` (one file per job, so parallel workers never share a file), plus a `manifest.json` with the args and git commit. Run ids starting with `dev` are gitignored. Use them for throwaway tests. Extra fields beyond the example (`model_key`, `thinking_tokens`, `llm_cached`, `render_s`, `video_path`, `scene_title`) are defined in `logging_utils.AttemptRecord`.

**Do not change this schema without updating `analyze.py`.** Append new fields; don't rename existing ones.

## Coding conventions

- Python 3.10+, type hints, small modules. Prompts live in `src/c2a/prompts/`, not in Python strings.
- Generated code must be **ManimCE only** (`from manim import *`). Reject or repair anything importing `manimlib` (3b1b's ManimGL) — a common hallucination.
- Each generated scene = exactly one `Scene` (or `VoiceoverScene`) subclass, with the class name dictated by the pipeline (e.g. `Scene2`) so the renderer knows what to call.
- Frame bounds: x ∈ [−7.11, 7.11], y ∈ [−4, 4] (default 16:9, `frame_height = 8`). Tell the LLM this explicitly.
- Every render is a subprocess with a timeout (default 120 s). Never `exec` LLM code in the main process.
- Post-processing of generated code is deliberately minimal (extract the code block, rename the Scene class). It applies to every condition, so it must not quietly fix the errors being measured.
- Every LLM call and render attempt goes through the logger. If it isn't logged, it didn't happen.
- Cache LLM responses (keyed by prompt hash + model + temperature) so reruns of analysis don't re-spend API money.
- `outputs/` and media files are gitignored; `results/` (logs, tables, figures) is committed.
- Secrets in `.env`, never committed.

## Git and attribution

- **Never add Claude as an author or co-author.** No `Co-Authored-By: Claude` trailer in commits, no "Generated with Claude Code" line in PRs, no Claude/bot git identity. The GitHub contributor list must show only Jonah and Koray. This overrides any default attribution behavior.
- Commit with the human's own git identity (whatever `git config user.name/user.email` says). Don't change it.
- Commit after each chunk of work, split into small logical commits. **Never push** unless asked.

## Layout checker approach

Instrument the scene rather than analyzing pixels:
- Patch `Scene.play` / `Scene.wait` (or inject a mixin base class) so that after each animation it snapshots every top-level mobject in `self.mobjects` with its bounding box (`get_left()`, `get_right()`, `get_top()`, `get_bottom()`).
- **Off-frame:** any bbox extending beyond the frame bounds (with a small margin, e.g. 0.1).
- **Overlap:** pairwise bbox intersection over the smaller box's area above a threshold (start at 0.15). Ignore intentional containment: a label inside its own shape, objects grouped in the same `VGroup`, and background elements like `NumberPlane`/`Axes` vs. things drawn on them.
- Write defects to a JSON sidecar that `layout.py` reads back. Defect descriptions go to the LLM in plain language ("the MathTex 'P(A|B)' overlaps the Arrow at step 3; move it up").

## Team

- **Jonah:** the whole `zero_shot` baseline end to end (env, LLM client, midterm concept subset, planner + zero-shot codegen prompts, render harness, logging, pipeline, ablation runner), then repair loops, layout checker, metrics/analysis, demo app.
- **Koray:** few-shot curation, RAG corpus + retriever, narration. Builds on Jonah's baseline harness (`llm.py`, `codegen.py`, logger) rather than a parallel one.
- **Both:** human ratings (midterm and final), reports.

## Course deliverables

- **Midterm check-in report** (source: `report/reference/course/midterm_requirements.pdf`, kept local and not committed). 2–3 pages, 11 pt, 1" margins, single column, figures encouraged, **team name and roles at the top of page 1**. Purpose: show progress, and **get feedback on data, models and experimental design**. That's the place to explain the model-plan change. Sections and page budgets:
  1. **Project Overview** (½ p): research question, motivation, link to course topics.
  2. **Dataset** (½ p): source, size, preprocessing, ethical considerations.
  3. **Methods** (1 p): technical design, model/prompt strategy, **system diagram**.
  4. **Preliminary Results** (½–1 p): metrics, qualitative outputs, early insights.
  5. **Next Steps** (½ p): planned improvements, evaluation strategy, open questions.

  Rubric (100): Problem Definition 15 (clear question, motivation, relevance to course) · Dataset 15 (appropriate, well-described, ethically considered) · Methodology 25 (sound and *creative* technical approach) · Preliminary Results 25 (evidence of progress *with interpretation and visuals*) · Writing & Organization 10 · Reflection & Next Steps 10 (realistic, thoughtful plan).
  The example report (`report/reference/course/midterm_example.pdf`) is a LaTeX article: title, names, roman-numeral sections (I. Project Overview … V. Next Steps), one full-width system-diagram figure with a caption, qualitative examples written as prose (one success, one contrasting failure), and a small booktabs-style table of baseline vs. improved method. Match that style.
  **Changes since the proposal must be explained** (`report/reference/Project_Proposal_Femiani_Bayram.pdf`): GPT/OpenAI → Gemini 3.5 Flash; open model (LLaMA-2/Qwen) → dropped from the main study (Qwen2.5-Coder was tried, output too poor); LangChain → plain Python (exact logging of every call); 40 concepts → 6 (2 per tier).
  **Midterm scope (agreed with Dr. Zhang):** 6 concepts (20 scenes), `zero_shot` vs. `zero_shot_repair` on Gemini, **plus human ratings** (correctness and clarity, 1–5). **Due Fri 2026-11-13, midnight.** Submit the PDF (required), plus the repo link and a few sample videos.
- **Final:** full ablation table (technique by condition on Gemini; extra models optional), human ratings by tier, success/failure gallery, working demo, final report.

## Gotchas

- LaTeX must be installed for `MathTex`/`Tex`. If LaTeX errors dominate, log them as `latex` and consider a prompt rule or fallback.
- Manim's API changed a lot between versions; old tutorials and LLM training data use deprecated calls (`get_graph`, `ShowCreation`, `TextMobject`, `TexMobject`). Pin the ManimCE version in requirements and say it in prompts.
- `manim-voiceover` can use gTTS (free) or OpenAI TTS. Use gTTS for experiments; narration doesn't affect the render/layout metrics.
- Rendering is the bottleneck. Parallelize across concepts with a process pool, not threads.
- Manim **exits 0 even when the requested Scene class doesn't exist**: it renders whatever class it finds. `render.py` therefore checks that `<SceneName>.mp4` was written by this render, not just the return code.
- `Mobject.__getattr__` fabricates any `get_*` method, so hallucinated calls like `Axes.get_graph(f)` fail as a **TypeError** ("getter() takes 1 positional argument"), not an AttributeError. The classifier maps this to `hallucinated_api`.
- Rich tracebacks wrap at terminal width and truncate error messages. `render.py` sets `COLUMNS=400` for the subprocess.
- Gemini 3.x spends "thinking" tokens before answering. They count toward rate limits and are logged as `thinking_tokens`.