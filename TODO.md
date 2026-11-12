# TODO — Concept-to-Animation

Check items off as they're done. See `CLAUDE.md` for project context, conventions, and the log schema.
Owner tags: **[J]** Jonah, **[K]** Koray, **[J+K]** both.

Phases follow the build order: one phase per ablation layer, each ending with a quick check that the new layer works. The real experiment runs are all in the testing phase, so every condition is measured the same way with the same code.

---

## Phase 0 — Setup
- [x] [J] Create GitHub repo; commit `CLAUDE.md` + `TODO.md`
- [x] [J] Python env + `requirements.txt` (pin `manim`, `manim-voiceover[gtts]`, `google-genai`, `python-dotenv`, `pydantic`, `pandas`, `matplotlib`, `pytest`)
- [x] [J] `.env.example`, `.gitignore` (`outputs/`, media, `.env`, caches)
- [x] [J] System deps (ffmpeg, cairo/pango, LaTeX, sox) + test render on Jonah's machine
- [x] [J] Decide models: **codegen = Qwen2.5-Coder 7B vs 3B** (size is the only variable), 4-bit via Ollama; **planner = gemini-3.5-flash**. Cost: $0
- [ ] [J] Set up the home PC (headless Ubuntu, GTX 1660 Super): clone, README setup, Ollama service with `OLLAMA_CONTEXT_LENGTH=8192`, pull both Qwen tags, `scripts/check_open_model.py` for each; note tok/s
- [ ] [J] Run `zero_shot` on the 12 midterm concepts with `--models qwen7b qwen3b` on the home PC
- [ ] [J] Add Koray as collaborator (need his GitHub username)
- [ ] [K] System deps + test render with `manim -ql` on Koray's machine
- [ ] [K] Check what GPU + VRAM his gaming PC has
- [ ] [J+K] Tell Dr. Zhang the model plan: Qwen2.5-Coder 7B vs 3B for codegen (instead of GPT + LLaMA-2), Gemini as planner

## Phase 1 — Zero-shot baseline (`zero_shot`)
Goal: `python experiments/run_ablation.py --conditions zero_shot --models gemini --limit 12` runs end to end and writes logs.
- [x] [J] `data/concepts.json`: 12-concept midterm subset (4 per tier)
- [x] [J] `config.py`: conditions, models, budgets, paths
- [x] [J] `llm.py`: Gemini client with response caching, token counting, retry/backoff for free-tier rate limits
- [x] [J] `render.py`: subprocess render with timeout → `(success, stderr_tail, video_path)`
- [x] [J] Error classifier → `hallucinated_api | bad_signature | latex | timeout | syntax | other`
- [x] [J] `logging_utils.py`: JSONL logger following the schema in `CLAUDE.md`
- [x] [J] Planner prompt + `planner.py` → validated storyboard JSON (pydantic); cache to `data/storyboards/`
- [x] [J] Zero-shot codegen prompt + `codegen.py`; strip markdown fences; enforce class name
- [x] [J] `pipeline.py`: concept → storyboard → per-scene code → render → stitch scene videos
- [x] [J] `experiments/run_ablation.py` with `--conditions`, `--models`, `--limit`, `--concepts`
- [x] [J] `experiments/analyze.py`: render success, first-try success, error-type breakdown, by condition × model × tier
- [x] [J] Unit tests: error classifier, code extraction, storyboard validation
- [ ] [J] Check: run on 2–3 concepts, watch the videos, read the failures
- [ ] [J] **Blocker: Gemini free tier = 20 requests/day/model.** Full 12-concept zero-shot run needs ~42 calls. Decide: paid key / credits, or spread over days

## Phase 2 — + Error repair (`zero_shot_repair`)
- [ ] [J] `repair.py`: render-and-repair loop (code + traceback → fixed code, ≤ N=3 retries), every attempt logged
- [ ] [J] Repair prompt in `prompts/`
- [ ] [J] Avg repair iterations metric in `analyze.py`
- [ ] [J] Check: a scene that crashes zero-shot gets fixed by repair

### Midterm checkpoint (after Phase 2)
- [ ] [J] Run `zero_shot` vs `zero_shot_repair` on the 12-concept subset, qwen7b + qwen3b (midterm uses the current 12 storyboards)
- [ ] [J] Figures: success-rate bar chart by tier; error-type stacked bar
- [ ] [J+K] Pick 2–3 qualitative examples (one clean success, one hallucinated-API crash, one layout mess) and screenshot frames
- [ ] [J+K] System diagram (pipeline figure) for Methods
- [ ] [J+K] Set up LaTeX report in `report/midterm/` (Overleaf or local), matching the example's style (see CLAUDE.md "Course deliverables")
- [ ] [J+K] Write midterm report (2–3 pp, 11 pt, 1" margins, single column, team name + roles on top). Page budgets: Overview ½, Dataset ½, Methods 1, Results ½–1, Next Steps ½
  - [ ] Overview: research question, motivation, link to course topics (prompting, RAG, self-refinement, code generation)
  - [ ] Dataset: concept tiers, Manim docs corpus, preprocessing, ethics (no personal data; risk of confident but wrong math explanations → human correctness ratings)
  - [ ] Methods: pipeline, prompt strategy, repair loop, diagram; **changes since the proposal** (Gemini planner, Qwen 7B vs 3B via Ollama, no LangChain) and why (free-tier limits, cost, size as a clean variable)
  - [ ] Preliminary Results: table + figures + qualitative examples (one success, one contrasting failure, as prose with frames) + **interpretation** (rubric weights it)
  - [ ] Next Steps: few-shot, RAG, layout repair, open model, voiceover, human eval, demo
- [ ] [J+K] Proofread against the rubric; submit

## Phase 3 — + Few-shot (`few_shot`)
- [ ] [K] Curate 3–5 example scenes into `data/fewshot/` (short, modern ManimCE; cover Axes/graphs, MathTex, shapes+arrows, transforms)
- [ ] [K] Inject examples into the codegen prompt when the condition says so
- [ ] [K] Check: few-shot output uses the modern API on a few scenes

## Phase 4 — + RAG (`rag`, `rag_repair`)
- [ ] [K] Download ManimCE docs + example gallery into `data/manim_docs/` (record version + license: MIT)
- [ ] [K] `rag.py`: chunk docs, embed (e.g. `all-MiniLM-L6-v2`), FAISS/Chroma index; retrieve top-k by scene description; inject into prompt
- [ ] [K] Check retrieval quality on a handful of scenes (does it pull the right classes, like `Axes.plot` for graphs?)

## Phase 5 — + Layout repair (`rag_repair_layout`)
- [ ] [J] `layout.py`: instrumented scene base / patched `play`+`wait` → bbox snapshots → JSON sidecar
- [ ] [J] Overlap + off-frame detection with containment/group exclusions; tune thresholds on ~10 hand-labeled scenes
- [ ] [J] Layout-repair loop (defects in plain language → LLM → re-render, ≤ M=2 retries)
- [ ] [J] Layout-defect rate metric in `analyze.py`

## Phase 6 — Open model, narration, demo
- [ ] [K] Extend `data/concepts.json` to all 40 concepts, 3 tiers (~13 each)
- [ ] [K] Generate storyboards for the 28 new concepts with the **same planner** (`gemini-3.5-flash`): `python -c "from c2a.planner import *; [get_storyboard(c) for c in load_concepts()]"` (skips existing ones; ~20 free calls/day, so it takes 2 days). Read them over and fix any garbled text by hand
- [ ] [K] `narration.py`: convert scenes to `VoiceoverScene`, gTTS backend; sync `with self.voiceover(text=...)` blocks
- [ ] [J] `app/`: simple Gradio or Streamlit UI (type concept → progress log → video, with storyboard + code alongside)

## Phase 7 — Testing (the real experiment runs)
Same code, same storyboards, fixed temperature/seed, same machine (home PC). Check every run with `--limit 5` first.
- [ ] [J+K] **Regenerate all 40 storyboards in one batch with one planner model** (fixes the midterm model-drift issue; see CLAUDE.md "Known inconsistency"). Check that `model_version` matches across all 40
- [ ] [J+K] Test `zero_shot` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] Test `zero_shot_repair` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] Test `few_shot` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] Test `rag` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] Test `rag_repair` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] Test `rag_repair_layout` × qwen7b/qwen3b × 40 concepts
- [ ] [J+K] (If budget allows) leave-one-out rows: `full_minus_rag`, `full_minus_fewshot`
- [ ] [J] Final results table: render success, avg repair iterations, layout-defect rate per condition × model
- [ ] [J] Breakdown by tier (does performance drop for abstract concepts?)
- [ ] [J] Token cost + latency per condition
- [ ] [J+K] Human evaluation: sample ~20 final videos stratified by tier; both rate correctness + clarity 1–5 blind to condition; record in `results/human_ratings.csv`; report inter-rater agreement
- [ ] [J+K] Success/failure gallery: thumbnails + short captions, incl. where abstract concepts break down

## Phase 8 — Final report + demo
- [ ] [J+K] Record a short demo video as backup in case live rendering is slow
- [ ] [J+K] Final report: best configuration, ablation analysis, human eval, gallery, limitations, future work
- [ ] [J+K] Clean repo: README with setup + reproduce-results commands

---

## Open questions
- [ ] Dr. Zhang OK with Qwen 7B vs 3B instead of GPT + LLaMA-2? (LLaMA-2 and Gemini are still one flag away)
- [ ] Midterm report due date? Final due date? → add dates here
- [ ] Is concatenated multi-scene video required for metrics, or per-scene only? (Plan: metrics per scene, demo stitches)
- [ ] Overlap threshold + what counts as "intentional" overlap — define with a few labeled examples before trusting the metric
