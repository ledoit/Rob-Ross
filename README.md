# Rob Ross palette OS (phase 1 MVP)

Local-first palette generation engine that learns a user's aesthetic from heterogeneous taste sources and compiles it into a versioned design genome.

Repository: [github.com/ledoit/Rob-Ross](https://github.com/ledoit/Rob-Ross)

If your checkout folder is still named `robross-palette-engine`, you can rename it to `rob-ross-palette-engine` locally (close editors first if Windows reports “permission denied”).

## Core principles

- 100% local execution
- No paid APIs
- No cloud dependencies at runtime
- Deterministic color math done in code (not by LLM)

## Stack

- Python 3.11+
- Ollama (`mistral` or `llama3`)
- LlamaIndex
- ChromaDB
- sentence-transformers
- colormath
- Rich
- Typer

## Quick start

1. Create environment:
   - `python -m venv .venv`
   - Windows Bash: `source .venv/Scripts/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Install Ollama and pull a local model:
   - Install from [https://ollama.com/download](https://ollama.com/download)
   - Run:
     - `ollama pull mistral`
     - or `ollama pull llama3`
4. Optional environment variables (prefer `ROB_ROSS_*`; legacy `ROBROSS_*` still works):
   - `setx ROB_ROSS_OLLAMA_MODEL mistral` (PowerShell: `$env:ROB_ROSS_OLLAMA_MODEL="mistral"` for session only)
   - `setx ROB_ROSS_EMBED_MODEL sentence-transformers/all-MiniLM-L6-v2`
5. Run CLI:
   - `python cli.py --help`

## Commands

- `python cli.py ingest <source>`
- `python cli.py build-genome`
- `python cli.py generate --task "make 11 ide palettes and 5 web palettes then build a superset of 25"`
- `python cli.py quick "black and yellow"` — prompt-driven IDE batch (`--variety`, `--adherence`, `--fresh` to wipe `ide_palette_*.json` first)
- Taste moods are **weighted-sampled** per batch when `genome/user_loop_state.json` exists (auto-created on first `quick`). Hearts / `roster add` / `roster shortlist add` bump weights. Optional reproducibility: `ROB_ROSS_SEED=12345`.
- `python cli.py preview` — HTML mock-editor gallery
- `python cli.py roster add ide_palette_02` — **final** pick (VS Code export list); alias `roster export-add`
- `python cli.py roster shortlist add ide_palette_02` — **shortlist** (best-of-batch; biases the next `quick` only)
- `python cli.py export-themes`
- `python cli.py feedback`
- `python cli.py superset --input-palettes outputs/palettes --count 25`

## Layout

- `genome/` genome JSON, `theme_roster.json` (export + shortlist), `user_loop_state.json` (taste mood weights + event tail), history snapshots
- `sources/` raw and processed extracted principles
- `vector_store/` Chroma persistence (`rob_ross_principles` collection)
- `outputs/palettes/` generated palettes JSON
- `outputs/reports/` rationale markdown reports
- `core/` implementation modules
- `tests/` unit tests
- `scripts/export_vscode_themes.py` — installable Cursor/VS Code themes (`rob-ross-ide-palettes`)
- `vscode-themes/` local theme extension package
