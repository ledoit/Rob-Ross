# RR IDE themes

Generated from `outputs/palettes/ide_palette_*.json`.

## Build VSIX locally

1. `npm i -g @vscode/vsce`
2. `cd vscode-themes`
3. `vsce package`
4. In Cursor/VSCode: Extensions -> ... -> Install from VSIX

## Regenerate themes

- From project root: `python cli.py export-themes` (themes JSON only)
- Export + install into Cursor: `python -c "from pathlib import Path; from core.ide_theme import finalize_ide_themes; finalize_ide_themes(Path('.'))"`

VSIX files are local install artifacts (gitignored); rebuild with the commands above.