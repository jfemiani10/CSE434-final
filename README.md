# Concept-to-Animation

CSE 434 (Generative AI) final project, Miami University, Fall 2026. Jonah Femiani and Koray Bayram.

Type in a math or CS concept ("binary search", "the Pythagorean theorem") and get a narrated explainer video built with [Manim Community Edition](https://www.manim.community/), in the style of 3Blue1Brown.

The research question is which generative techniques make LLM-written animation code actually render, and look clean. LLMs often call Manim functions that don't exist or put objects on top of each other. We compare setups from a plain prompt up to the full pipeline (few-shot examples, retrieval of Manim docs, an error-repair loop and a layout-repair loop), on 6 concepts in three difficulty tiers, using Gemini 3.5 Flash to plan storyboards and write the code.

```
concept → planner (storyboard) → code generator → render ⟲ fix errors → layout check ⟲ fix overlaps → narration → video
```

See [CLAUDE.md](CLAUDE.md) for the full design (experiment conditions, metrics, log format) and [TODO.md](TODO.md) for who's doing what.

## Setup (Ubuntu / WSL)

**1. System packages** (needs sudo, one time):

```bash
sudo apt update
sudo apt install -y python3.12-venv build-essential pkg-config python3-dev \
    ffmpeg sox libcairo2-dev libpango1.0-dev \
    texlive texlive-latex-extra texlive-fonts-extra
```

- `ffmpeg` stitches frames into video.
- `cairo` draws the shapes. `pango` lays out text.
- `sox` is used by manim-voiceover for audio. Without it, every `manim` command prints a warning.
- LaTeX typesets math (`MathTex`). This is the biggest download, around 1–2 GB.

On macOS: `brew install py3cairo ffmpeg pango pkg-config` and install [MacTeX](https://www.tug.org/mactex/). On Windows, use WSL.

**2. Python environment:**

```bash
git clone https://github.com/jfemiani10/CSE434-final.git
cd CSE434-final
python3 -m venv .venv
source .venv/bin/activate        # do this in every new terminal
pip install -r requirements.txt
pip install -e .                 # makes `import c2a` work from anywhere
```

**3. API key:**

```bash
cp .env.example .env
# paste your Gemini key from https://aistudio.google.com/apikey into .env
```

**4. Check it works:**

```bash
manim checkhealth
```

**5. (Optional) Local models.** Qwen2.5-Coder 7B/3B via Ollama are registered as extra models but aren't part of the main experiment. Setup is in the next section and needs an NVIDIA GPU with at least 6 GB of VRAM.

**Gemini quota:** the free tier allows only 20 requests per day per model, which isn't enough for a full run. Use a key with billing enabled (AI Studio → API keys → set up billing).

## Optional: local models on a GPU box (headless Ubuntu)

Only needed for the optional Qwen comparison. Tested target: a headless Ubuntu PC with a GTX 1660 Super, over SSH. One-time setup on that machine:

```bash
nvidia-smi                       # must show the GPU. If not: sudo ubuntu-drivers install && sudo reboot
# then do steps 1-4 above (apt packages, clone, venv, .env)
```

The `.env` there only needs `GEMINI_API_KEY` if you'll plan *new* storyboards. Existing ones are committed in `data/storyboards/`.

**Ollama as a background service.** The install script sets up a systemd service that starts on boot:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl edit ollama       # opens an editor; add these two lines, save, quit:
#   [Service]
#   Environment="OLLAMA_CONTEXT_LENGTH=8192"
sudo systemctl restart ollama
```

The context-length line matters. Ollama's default context is small, and it **silently cuts off** longer prompts. The prompts would still "work", but the model would never see the end of them.

```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M      # ~4.7 GB
ollama pull qwen2.5-coder:3b-instruct-q4_K_M      # ~1.9 GB
python scripts/check_open_model.py --model qwen7b # writes one scene, renders it, prints tokens/sec
python scripts/check_open_model.py --model qwen3b
ollama ps                                         # while a model is loaded: shows GPU use and context size
```

**Long runs: use tmux** so the run keeps going after you disconnect:

```bash
tmux new -s run                  # opens a terminal that survives logout
source .venv/bin/activate
python experiments/run_ablation.py --conditions zero_shot --models qwen7b qwen3b --midterm
# detach: Ctrl+B then D. Log out; the run keeps going.
tmux attach -t run               # later: reattach to check on it
```

**Viewing results from your laptop.** The review page and videos are on the box. Serve them over an SSH tunnel:

```bash
# on the box:
python -m http.server 8000 --directory outputs
# on your laptop (new terminal):
ssh -L 8000:localhost:8000 <user>@<home-pc>
# then open http://localhost:8000/<run_id>/review.html in your laptop's browser
```

Or copy a run to your laptop: `rsync -av <user>@<home-pc>:CSE434-final/outputs/<run_id> outputs/`. VS Code's Remote-SSH extension also works for browsing code and logs on the box.

## Usage

```bash
source .venv/bin/activate

# one concept, end to end (prints per-scene results and the stitched video path)
python -m c2a.pipeline --concept pythagorean_theorem --condition zero_shot --model gemini

# a batch: all 6 concepts, zero-shot, Gemini (--workers 1 avoids per-minute rate limits)
python experiments/run_ablation.py --conditions zero_shot --models gemini --workers 1

# metrics for a run (the runner prints the exact command at the end)
python experiments/analyze.py results/logs/<run_id>

pytest   # unit tests (no API calls)
```

## Reviewing a run

Every run has a **run id** (e.g. `2026-11-10_2205_de9f`). The runner prints it at the start and end. `python experiments/review.py --list` lists them all.

**The easy way: the review page.**

```bash
python experiments/review.py <run_id>
explorer.exe "$(wslpath -w outputs/<run_id>/review.html)"     # opens it in your Windows browser
```

The page has a summary table (scenes rendered per concept), then one section per concept with:
- the concept's one-line prompt and the full storyboard the planner made;
- for every scene: pass/fail, the error message, the video, and click-to-expand panels with the **exact prompt sent to the model**, the **code that was rendered**, the model's **raw reply** and the **error output**.

**The numbers:** `python experiments/analyze.py results/logs/<run_id>` prints success rates by condition, model and tier, a count of each error type and every failure message. It also saves CSVs to `results/tables/`.

**Where the files are, if you want to dig by hand:**

| What | Where |
|---|---|
| Concept list | `data/concepts.json` |
| Storyboard (planner output) | `data/storyboards/<concept>.json` |
| Prompt templates | `src/c2a/prompts/*.md` |
| Per scene, per attempt | `outputs/<run_id>/<condition>__<model>/<concept>/scene_<i>_attempt_<a>.*`: `.prompt.md` (what went in), `.raw.md` (model's reply), `.py` (code that was rendered), `.stderr.txt` (error output, failures only) |
| Scene videos | `outputs/<run_id>/.../media/scene_<i>_attempt_<a>/videos/.../Scene<i>.mp4` |
| Whole concept stitched together | `outputs/<run_id>/<condition>__<model>/<concept>/<concept>.mp4` (scenes that rendered) |
| Attempt log (one JSON line per attempt) | `results/logs/<run_id>/*.jsonl` |
| Run settings + git commit | `results/logs/<run_id>/manifest.json` |

To re-render one scene by hand (e.g. after editing the code to see what a fix needs): `manim -ql outputs/<run_id>/.../scene_2_attempt_1.py Scene2`.

`outputs/` is not committed (videos are big), so each person sees only runs made on their own machine. Logs in `results/logs/` are committed, except `dev*` runs.

Generated code, raw LLM replies, error output and videos land in `outputs/<run_id>/...`. LLM replies are cached in `.cache/llm/`, so rerunning the same thing costs nothing. Pass `--no-cache` to force fresh calls. Use a run id starting with `dev` (`--run-id dev_mytest`) for throwaway runs; those logs aren't committed.
