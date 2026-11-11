# Concept-to-Animation

CSE 434 (Generative AI) final project, Miami University, Fall 2026. Jonah Femiani and Koray Bayram.

Type in a math or CS concept ("Bayes' theorem", "binary search") and get a narrated explainer video built with [Manim Community Edition](https://www.manim.community/), in the style of 3Blue1Brown.

The research question is which generative techniques make LLM-written animation code actually render, and look clean. LLMs often call Manim functions that don't exist or put objects on top of each other. We compare five setups, from a plain prompt up to the full pipeline (few-shot examples, retrieval of Manim docs, an error-repair loop and a layout-repair loop), on 40 concepts and two models (Gemini and an open code model).

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

**5. Open model (optional, needs an NVIDIA GPU with ≥6 GB of VRAM):**

```bash
curl -fsSL https://ollama.com/install.sh | sh          # installs Ollama
OLLAMA_CONTEXT_LENGTH=8192 ollama serve                # leave running in its own terminal
ollama pull qwen2.5-coder:7b                           # ~4.7 GB download
python scripts/check_open_model.py                     # asks Qwen for a scene and renders it
```

## Usage

```bash
source .venv/bin/activate

# one concept, end to end (prints per-scene results and the stitched video path)
python -m c2a.pipeline --concept pythagorean_theorem --condition zero_shot --model gemini

# a batch: every midterm concept, zero-shot, Gemini
python experiments/run_ablation.py --conditions zero_shot --models gemini --midterm

# metrics for a run (the runner prints the exact command at the end)
python experiments/analyze.py results/logs/<run_id>

pytest   # unit tests (no API calls)
```

Generated code, raw LLM replies, error output and videos land in `outputs/<run_id>/...`. LLM replies are cached in `.cache/llm/`, so rerunning the same thing costs nothing. Pass `--no-cache` to force fresh calls. Use a run id starting with `dev` (`--run-id dev_mytest`) for throwaway runs; those logs aren't committed.
