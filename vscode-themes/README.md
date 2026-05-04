# Rob Ross IDE themes

Generated from `outputs/palettes/ide_palette_*.json`.

## Build VSIX locally

1. `npm i -g @vscode/vsce`
2. `cd vscode-themes`
3. `vsce package`
4. In Cursor/VS Code: Extensions -> ... -> Install from VSIX

## Regenerate themes

- From project root: `python scripts/export_vscode_themes.py`
