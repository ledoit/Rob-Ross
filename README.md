# RobRoss Palette OS (Phase 1 MVP)

Local-first palette generation engine that learns a user's aesthetic from heterogeneous taste sources and compiles it into a versioned design genome.

## Core Principles

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

## Quick Start

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
4. Optional environment variables:
   - `setx ROBROSS_OLLAMA_MODEL mistral` (PowerShell: `$env:ROBROSS_OLLAMA_MODEL="mistral"` for session only)
   - `setx ROBROSS_EMBED_MODEL sentence-transformers/all-MiniLM-L6-v2`
5. Run CLI:
   - `python cli.py --help`

## Commands

- `python cli.py ingest <source>`
- `python cli.py build-genome`
- `python cli.py generate --task "make 11 ide palettes and 5 web palettes then build a superset of 25"`
- `python cli.py feedback`
- `python cli.py superset --input-palettes outputs/palettes --count 25`

## Layout

See project folders:

- `genome/` genome JSON and history snapshots
- `sources/` raw and processed extracted principles
- `vector_store/` Chroma persistence
- `outputs/palettes/` generated palettes JSON
- `outputs/reports/` rationale markdown reports
- `core/` implementation modules
- `tests/` unit tests
- `scripts/export_vscode_themes.py` generate installable Cursor/VSCode themes
- `vscode-themes/` local theme extension package
