# TODO — Concept-to-Animation

Check items off as they're done. See `CLAUDE.md` for project context, conventions, and the log schema.
Owner tags: **[J]** Jonah, **[K]** Koray, **[J+K]** both.

---

## Tonight (Nov 10) — [J] zero-shot baseline, end to end
Goal: `python experiments/run_ablation.py --conditions zero_shot --models gemini --limit 12` runs and writes JSONL logs.
Covers the [J] items in Phase 0, the 12-concept subset, and Phase 2 minus `repair.py`.

## Phase 0 — Setup
- [x] [J] Create GitHub repo; commit `CLAUDE.md` + `TODO.md`
- [ ] [J] Add Koray as collaborator (need his GitHub username)
- [x] [J] Python env + `requirements.txt` (pin `manim`, `manim-voiceover[gtts]`, `google-genai`, `python-dotenv`, `pydantic`, `pandas`, `matplotlib`, `pytest`)
- [ ] [J+K] Install system deps: ffmpeg, cairo/pango, LaTeX, sox (Jonah ✓ except sox; Koray ☐)
- [ ] [J+K] Render a hand-written test scene with `manim -ql` on each person's machine (Jonah ✓; Koray ☐)
- [x] [J] `.env.example`, `.gitignore` (`outputs/`, media, `.env`, caches)
- [ ] [J+K] Ask Dr. Zhang to approve the open model (propose Qwen2.5-Coder-7B-Instruct instead of LLaMA-2)
- [x] [J] Decide where the open model runs: **Ollama, 4-bit, local GPU** (Jonah's 4050 for dev; Koray's gaming PC if faster; Colab T4 as fallback). Cost: $0 (OpenRouter no longer hosts the 7B)
- [ ] [J] Install Ollama, pull `qwen2.5-coder:7b`, run `scripts/check_open_model.py`; note tok/s
- [ ] [K] Check what GPU + VRAM his gaming PC has

## Phase 1 — Dataset
- [ ] [J] Write the **midterm subset** of 12 concepts (4 per tier) into `data/concepts.json` (needed for the baseline)
- [ ] [K] Extend `data/concepts.json` to all 40 concepts, 3 tiers (~13 each), with one-sentence descriptions
- [ ] [K] Curate 3–5 few-shot example scenes into `data/fewshot/` (short, modern ManimCE, cover Axes/graphs, MathTex, shapes+arrows, transforms)
- [ ] [K] Download ManimCE docs + example gallery into `data/manim_docs/` (record version + license: MIT)

## Phase 2 — Core harness (minimum for midterm)
- [ ] [J] `render.py`: subprocess render with timeout → `(success, stderr_tail, video_path)`
- [ ] [J] Error classifier → `hallucinated_api | bad_signature | latex | timeout | syntax | other`
- [ ] [J] `logging_utils.py`: JSONL logger following the schema in `CLAUDE.md`
- [ ] [J] `llm.py`: Gemini client wrapper with response caching, token counting, retry/backoff for free-tier rate limits
- [ ] [J] Planner prompt + `planner.py` → validated storyboard JSON (pydantic); cache to `data/storyboards/`
- [ ] [J] Codegen prompt (zero-shot) + `codegen.py`; strip markdown fences from output; enforce class name
- [ ] [J] `repair.py`: render-and-repair loop (code + traceback → fixed code, ≤ N=3 retries)
- [ ] [J] `pipeline.py`: concept → storyboard → per-scene code → render (+repair) → concatenate scene videos
- [ ] [J] Unit tests: error classifier, code extraction, storyboard validation

## Phase 3 — Midterm experiment + report
- [ ] [J] `experiments/run_ablation.py` with `--conditions`, `--models`, `--limit`, `--concepts`
- [ ] [J+K] Run `zero_shot` vs `rag_repair`… **or at minimum** `zero_shot` vs `zero_shot + repair` on the 12-concept subset, Gemini only
- [ ] [J] `experiments/analyze.py`: render success, first-try success, avg repairs, error-type breakdown, by condition and tier
- [ ] [J] Figures: success-rate bar chart by tier; error-type stacked bar
- [ ] [J+K] Pick 2–3 qualitative examples (one clean success, one hallucinated-API crash, one layout mess) and screenshot frames
- [ ] [J+K] Make the system diagram (pipeline figure) for Methods
- [ ] [J+K] Write midterm report (2–3 pp, 11 pt, 1" margins, team name + roles on top)
  - [ ] Overview: research question, motivation, link to course topics (prompting, RAG, self-refinement, code generation)
  - [ ] Dataset: concept tiers, Manim docs corpus, preprocessing, ethics (no personal data; risk of confident but wrong math explanations → human correctness ratings)
  - [ ] Methods: pipeline, prompt strategy, repair loop, diagram
  - [ ] Preliminary Results: table + figures + qualitative examples + interpretation
  - [ ] Next Steps: RAG, layout repair, open model, voiceover, human eval, demo
- [ ] [J+K] Proofread against the rubric; submit

## Phase 4 — Full pipeline
- [ ] [K] Few-shot condition: inject examples into codegen prompt
- [ ] [K] `rag.py`: chunk docs, embed (e.g. `all-MiniLM-L6-v2`), FAISS/Chroma index; retrieve top-k by scene description; inject into prompt
- [ ] [K] Check retrieval quality on a handful of scenes (does it pull the right classes, like `Axes.plot` for graphs?)
- [ ] [J] `layout.py`: instrumented scene base / patched `play`+`wait` → bbox snapshots → JSON sidecar
- [ ] [J] Overlap + off-frame detection with containment/group exclusions; tune thresholds on ~10 hand-labeled scenes
- [ ] [J] Layout-repair loop (defects in plain language → LLM → re-render, ≤ M=2 retries)
- [ ] [K] `narration.py`: convert scenes to `VoiceoverScene`, gTTS backend; sync `with self.voiceover(text=...)` blocks
- [ ] [J] Open-model client in `llm.py` (OpenAI-compatible → Ollama), same interface as Gemini

## Phase 5 — Full experiments
- [ ] [J+K] Run all 5 conditions × 2 models × 40 concepts (budget-check first with `--limit 5`)
- [ ] [J] Final results table: render success, avg repair iterations, layout-defect rate per condition × model
- [ ] [J] Breakdown by tier (does performance drop for abstract concepts?)
- [ ] [J] Token cost + latency per condition (useful for discussion)
- [ ] [J+K] Human evaluation: sample ~20 final videos stratified by tier; both rate correctness + clarity 1–5 blind to condition; record in `results/human_ratings.csv`; report inter-rater agreement
- [ ] [J+K] Success/failure gallery: thumbnails + short captions, incl. where abstract concepts break down

## Phase 6 — Demo + final report
- [ ] [J] `app/`: simple Gradio or Streamlit UI — type concept → progress log → video
- [ ] [J] Use the best-performing config by default; show storyboard + generated code alongside video
- [ ] [J+K] Record a short demo video as backup in case live rendering is slow
- [ ] [J+K] Final report: best configuration, ablation analysis, human eval, gallery, limitations, future work
- [ ] [J+K] Clean repo: README with setup + reproduce-results commands

---

## Open questions
- [ ] Which open model is approved? (Running Qwen2.5-Coder-7B for now; LLaMA-2 is one flag away. Confirm with Koray + Dr. Zhang.)
- [ ] Tell Dr. Zhang the closed model is Gemini (free student access) instead of GPT
- [ ] Midterm report due date? Final due date? → add dates here
- [ ] Is concatenated multi-scene video required for metrics, or per-scene only? (Plan: metrics per scene, demo stitches)
- [ ] Overlap threshold + what counts as "intentional" overlap — define with a few labeled examples before trusting the metric