# Rob Ross palette OS

Local-first palette generation: taste sources → versioned genome → IDE themes and website tokens.

Repository: [github.com/ledoit/Rob-Ross](https://github.com/ledoit/Rob-Ross)  
Local checkout: `Menhir Holdings/Color/Rob-Ross` (rename from `robross-palette-engine` when editors are closed if the folder still uses the old name)

## Core principles

- 100% local execution
- No paid APIs at runtime
- Deterministic color math in code (not LLM)

## Stack

Python 3.11+, Ollama, Typer, FastAPI + Alpine.js (Web Color Studio)

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Bash
pip install -r requirements.txt
python cli.py --help
```

**IDE themes (chat agents)** — see `AGENTS.md`:

```python
from core.ide_theme import make_ide_palette, iterate_ide_palette, keep_ide_palette
```

**Web Color Studio** (optional browser UI):

```bash
python -m studio
# http://127.0.0.1:8765/web
```

## Commands

| Area | Command |
|------|---------|
| Genome | `ingest`, `build-genome`, `feedback`, `superset` |
| IDE export | `export-themes` (repair); agents use `keep_ide_palette` |
| Web palettes | `web quick`, `web preview`, `web export`, `web sites` |
| Site sync | `web sync paid` — push kept IDE palettes → registered consumers |
| Consumers | `web consumers` — list `genome/web_consumers.json` |

Register any site in `genome/web_consumers.json` (path + format). Built-in site profiles: `reno`, `jobjeeves`, `photoport`, `paid`, `generic`.

## Layout

```
genome/           genome_v1.json, theme_roster.json, web_consumers.json
core/             ide_theme, ide_iteration, pathways/web, export/
outputs/palettes/ ide_palette_*.json, web_{site}_palette_*.json
outputs/web-tokens/  CSS per site
vscode-themes/    Cursor/VS Code extension (robross-ide-palettes)
studio/           Web Color Studio only (/web)
AGENTS.md         Chat agent instructions
```

## Development

```bash
pytest
```

Typical agent flow: `make_ide_palette` → `iterate_ide_palette` → `keep_ide_palette` → auto VSIX.  
After keeping themes: `python cli.py web sync paid` (or your consumer id).
