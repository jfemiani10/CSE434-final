# TODO — Concept-to-Animation

Check items off as they're done. See `CLAUDE.md` for project context, conventions, and the log schema.
Owner tags: **[J]** Jonah, **[K]** Koray, **[J+K]** both.

Phases follow the build order: one phase per ablation layer, each ending with a quick check that the new layer works. The real experiment runs are all in the testing phase, so every condition is measured the same way with the same code.

**Decisions (2026-11-13, confirmed with Dr. Zhang):** model swap from the proposal is OK → **Gemini 3.5 Flash** for planner + codegen (Qwen tried, too weak). **6 concepts total, 2 per tier** (Pythagorean theorem, derivative as slope; matrix multiplication, binary search; recursion, Big-O): 20 scenes. 4-bit quantization is OK if a local model is ever used. LangChain not expected. **Human ratings are part of the midterm.** Submit the PDF (required) plus the repo link and sample videos.

---

## Midterm — due TONIGHT, Fri 2026-11-13, midnight
- [ ] [J] **Enable billing on the Gemini API key** (free tier = 20 requests/day; tonight needs ~100+ calls; expected cost is pennies to a few dollars)
- [ ] [J] Finish `zero_shot` run on the 6 concepts (`--conditions zero_shot --models gemini --workers 1`): 11 of 20 scenes are cached, 9 new calls needed
- [ ] [J] Build Phase 2 (repair) and run `zero_shot_repair` on the 6 concepts
- [ ] [J] `analyze.py`: results table + figures (success rate by tier; error-type breakdown)
- [ ] [J+K] **Human ratings:** both rate every rendered scene from both conditions (shuffled, condition hidden) for correctness and clarity, 1–5; failed scenes score 0 automatically → `results/human_ratings.csv`; report mean per condition/tier (2 columns) + rater agreement
- [ ] [J+K] Pick qualitative examples (one clean success, one contrasting failure, e.g. hallucinated API or layout mess) and grab frames
- [ ] [J+K] System diagram (pipeline figure) for Methods
- [ ] [J+K] LaTeX report in `report/midterm/`, matching the example's style (see CLAUDE.md "Course deliverables"). 2–3 pp, 11 pt, 1" margins, single column, team name + roles on top. Page budgets: Overview ½, Dataset ½, Methods 1, Results ½–1, Next Steps ½
  - [ ] Overview: research question, motivation, link to course topics (prompting, RAG, self-refinement, code generation)
  - [ ] Dataset: 6 concepts in 3 tiers (20 scenes), storyboards, Manim docs corpus (planned), ethics (no personal data; risk of confident but wrong math explanations → human correctness ratings)
  - [ ] Methods: pipeline, prompt strategy, repair loop, diagram; **changes since the proposal** (GPT → Gemini; open model dropped after Qwen trial; no LangChain; 40 → 6 concepts) and why
  - [ ] Preliminary Results: table + figures + human ratings + qualitative examples (prose with frames) + **interpretation** (rubric weights it)
  - [ ] Next Steps: few-shot, RAG, layout repair, voiceover, final human eval, demo
- [ ] [J] Curate sample videos for submission: commit a few to `results/gallery/` (small, -ql) or share via Drive link
- [ ] [J] Push repo; proofread against the rubric; submit PDF + repo link + sample videos

## Phase 0 — Setup
- [x] [J] Create GitHub repo; commit `CLAUDE.md` + `TODO.md`
- [x] [J] Python env + `requirements.txt`
- [x] [J] `.env.example`, `.gitignore` (`outputs/`, media, `.env`, caches)
- [x] [J] System deps (ffmpeg, cairo/pango, LaTeX, sox) + test render on Jonah's machine
- [x] [J] Decide models: **Gemini 3.5 Flash** (planner + codegen). Qwen2.5-Coder 7B/3B via Ollama tried and dropped (quality); still registered as optional
- [x] [J+K] Tell Dr. Zhang the model plan (approved)
- [ ] [J] Add Koray as collaborator (need his GitHub username)
- [ ] [K] System deps + test render with `manim -ql` on Koray's machine

## Phase 1 — Zero-shot baseline (`zero_shot`)
- [x] [J] `data/concepts.json`: 6 concepts (2 per tier). This is the full set
- [x] [J] `config.py`, `llm.py`, `render.py` + error classifier, `logging_utils.py`, `planner.py`, `codegen.py`, `pipeline.py`
- [x] [J] `experiments/run_ablation.py`, `experiments/analyze.py`, `experiments/review.py`
- [x] [J] Unit tests: error classifier, code extraction, storyboard validation
- [x] [J] Storyboards for all 6 concepts (gemini-3.5-flash, 2026-11-10)
- [ ] [J] Check: watch the videos, read the failures (review page)

## Phase 2 — + Error repair (`zero_shot_repair`)
- [ ] [J] `repair.py`: render-and-repair loop (code + traceback → fixed code, ≤ N=3 retries), every attempt logged
- [ ] [J] Repair prompt in `prompts/`
- [ ] [J] Avg repair iterations metric in `analyze.py`
- [ ] [J] Check: a scene that crashes zero-shot gets fixed by repair

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

## Phase 6 — Narration + demo
- [ ] [K] `narration.py`: convert scenes to `VoiceoverScene`, gTTS backend; sync `with self.voiceover(text=...)` blocks
- [ ] [J] `app/`: simple Gradio or Streamlit UI (type concept → progress log → video, with storyboard + code alongside)

## Phase 7 — Testing (the real experiment runs, Gemini, 6 concepts)
Same code, same storyboards, fixed temperature/seed. Check every run with `--limit 2` first.
- [ ] [J+K] Test `zero_shot`, `zero_shot_repair`, `few_shot`, `rag`, `rag_repair`, `rag_repair_layout`
- [ ] [J+K] (If time allows) leave-one-out rows: `full_minus_rag`, `full_minus_fewshot`
- [ ] [J+K] (Optional) repeat a few conditions with an extra model (e.g. `qwen7b`) for comparison
- [ ] [J] Final results table: render success, avg repair iterations, layout-defect rate per condition
- [ ] [J] Breakdown by tier (does performance drop for abstract concepts?)
- [ ] [J] Token cost + latency per condition
- [ ] [J+K] Human evaluation on final videos, stratified by tier, blind to condition; inter-rater agreement
- [ ] [J+K] Success/failure gallery: thumbnails + short captions, incl. where abstract concepts break down

## Phase 8 — Final report + demo
- [ ] [J+K] Record a short demo video as backup in case live rendering is slow
- [ ] [J+K] Final report: best configuration, ablation analysis, human eval, gallery, limitations, future work
- [ ] [J+K] Clean repo: README with setup + reproduce-results commands

---

## Open questions
- [x] Model swap OK with Dr. Zhang (yes, as long as changes aren't too large)
- [x] Midterm report due **Friday 2026-11-13, midnight**
- [ ] Final due date? → add here
- [ ] Is concatenated multi-scene video required for metrics, or per-scene only? (Plan: metrics per scene, demo stitches)
- [ ] Overlap threshold + what counts as "intentional" overlap — define with a few labeled examples before trusting the metric
