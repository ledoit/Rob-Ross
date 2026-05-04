"""Generate installable VSCode/Cursor themes from IDE palette JSON files."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.math_engine import hex_to_hsl, hsl_to_hex


def _load_palette(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bump_patch_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return "0.0.1"
    major, minor, patch = [int(p) for p in parts]
    return f"{major}.{minor}.{patch + 1}"


def _role_map(palette: dict) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            m[role] = hx
    return m


def _tone(hex_color: str, l_shift: float = 0.0, s_shift: float = 0.0) -> str:
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, max(0, min(100, s + s_shift)), max(0, min(100, l + l_shift)))


def _style_name(palette: dict) -> str:
    taste_context = str(palette.get("taste_context", ""))
    parts = taste_context.split(":")
    if len(parts) >= 2:
        return parts[1]
    return "core"


def _theme_mode(palette: dict) -> str:
    taste_context = str(palette.get("taste_context", ""))
    parts = taste_context.split(":")
    if len(parts) >= 3 and parts[2] in {"light", "dark"}:
        return parts[2]
    return "dark"


STYLE_CHROME_PROFILES = {
    "dracula_punch": {"bar_lift": 2, "selection_alpha": "66", "focus": "accent"},
    "fjord_hammer": {"bar_lift": 4, "selection_alpha": "4A", "focus": "accent"},
    "alpenglow_paper": {"bar_lift": 4, "selection_alpha": "3C", "focus": "muted"},
    "kimbie_warm": {"bar_lift": 3, "selection_alpha": "5A", "focus": "accent2"},
    "ion_storm": {"bar_lift": 0, "selection_alpha": "7E", "focus": "accent"},
    "forest_canopy": {"bar_lift": 2, "selection_alpha": "56", "focus": "accent2"},
    "void_forge": {"bar_lift": 0, "selection_alpha": "72", "focus": "accent2"},
    "bonfire_gold": {"bar_lift": 4, "selection_alpha": "68", "focus": "accent2"},
    "candy_voltage": {"bar_lift": 2, "selection_alpha": "7A", "focus": "accent"},
    "night_siren": {"bar_lift": 0, "selection_alpha": "7A", "focus": "accent2"},
    "high_contrast_signal": {"bar_lift": 0, "selection_alpha": "88", "focus": "accent"},
}


def _theme_json(palette: dict) -> dict:
    roles = _role_map(palette)
    bg = roles.get("background", "#1E1E2E")
    fg = roles.get("foreground", "#CDD6F4")
    surface = roles.get("surface", bg)
    muted = roles.get("muted", "#6C7086")
    accent1 = roles.get("accent_primary", "#89B4FA")
    accent2 = roles.get("accent_secondary", "#CBA6F7")
    syntax = [roles.get(f"syntax_{i}") for i in range(1, 7)]
    syntax = [c for c in syntax if c]
    while len(syntax) < 6:
        syntax.append(accent1 if len(syntax) % 2 == 0 else accent2)

    string_color = syntax[0]
    type_color = syntax[1]
    number_color = syntax[2]
    keyword_color = syntax[3]
    function_color = syntax[4]
    invalid_color = syntax[5]

    family = palette.get("hue_family", "core").title()
    style = _style_name(palette)
    theme_mode = _theme_mode(palette)
    style_label = style.replace("_", " ").title() if style else family
    name = f"RR {style_label}"
    chrome = STYLE_CHROME_PROFILES.get(style, {"bar_lift": 2, "selection_alpha": "55", "focus": "accent"})
    panel_bg = _tone(surface, l_shift=chrome["bar_lift"])
    bar_bg = _tone(bg, l_shift=max(0, chrome["bar_lift"] - 1))
    focus_border = accent1 if chrome["focus"] == "accent" else accent2 if chrome["focus"] == "accent2" else muted
    return {
        "name": name,
        "type": theme_mode,
        "colors": {
            "editor.background": bg,
            "editor.foreground": fg,
            "editorCursor.foreground": accent1,
            "editor.lineHighlightBackground": surface + "40",
            "editor.selectionBackground": accent1 + chrome["selection_alpha"],
            "editor.inactiveSelectionBackground": muted + "66",
            "editorIndentGuide.background1": muted + "66",
            "editorIndentGuide.activeBackground1": accent1 + "88",
            "editorWhitespace.foreground": muted + "88",
            "sideBar.background": panel_bg,
            "sideBar.foreground": fg,
            "activityBar.background": bar_bg,
            "activityBar.foreground": fg,
            "statusBar.background": panel_bg,
            "statusBar.foreground": fg,
            "titleBar.activeBackground": bar_bg,
            "titleBar.activeForeground": fg,
            "panel.background": panel_bg,
            "panel.border": muted,
            "terminal.background": bg,
            "terminal.foreground": fg,
            "terminal.ansiBlue": accent1,
            "terminal.ansiMagenta": accent2,
            "terminal.ansiGreen": string_color,
            "terminal.ansiRed": invalid_color,
            "terminal.ansiYellow": number_color,
            "focusBorder": focus_border,
            "button.background": accent1,
            "button.foreground": bg,
            "button.hoverBackground": accent2,
        },
        "tokenColors": [
            {"scope": ["comment", "punctuation.definition.comment"], "settings": {"foreground": muted}},
            {"scope": ["keyword", "storage", "storage.type"], "settings": {"foreground": keyword_color}},
            {"scope": ["entity.name.function", "support.function"], "settings": {"foreground": function_color}},
            {"scope": ["string", "constant.other.symbol"], "settings": {"foreground": string_color}},
            {"scope": ["constant.numeric", "constant.language"], "settings": {"foreground": number_color}},
            {"scope": ["variable", "meta.definition.variable.name"], "settings": {"foreground": fg}},
            {"scope": ["entity.name.type", "support.type"], "settings": {"foreground": type_color}},
            {"scope": ["invalid", "invalid.illegal"], "settings": {"foreground": invalid_color}},
            # JS/TS identity
            {"scope": ["support.class.component.js", "entity.name.type.class.ts"], "settings": {"foreground": type_color}},
            {"scope": ["entity.name.type.module.js", "support.type.primitive.ts"], "settings": {"foreground": keyword_color}},
            # Python identity
            {"scope": ["storage.type.function.python", "entity.name.function.decorator.python"], "settings": {"foreground": function_color}},
            {"scope": ["support.type.python", "entity.name.class.python"], "settings": {"foreground": type_color}},
            # JSON identity
            {"scope": ["support.type.property-name.json"], "settings": {"foreground": accent2}},
            {"scope": ["constant.language.json"], "settings": {"foreground": keyword_color}},
            # Markdown identity
            {"scope": ["markup.heading.markdown", "markup.bold.markdown"], "settings": {"foreground": accent1}},
            {"scope": ["markup.italic.markdown", "markup.inline.raw.string.markdown"], "settings": {"foreground": string_color}},
            # Shell identity
            {"scope": ["support.function.builtin.shell", "keyword.operator.pipe.shell"], "settings": {"foreground": function_color}},
            {"scope": ["variable.other.normal.shell"], "settings": {"foreground": type_color}},
        ],
    }


def main() -> None:
    package_vsix = "--no-package-vsix" not in sys.argv
    root = ROOT
    palettes_dir = root / "outputs" / "palettes"
    ext_dir = root / "vscode-themes"
    themes_dir = ext_dir / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)

    ide_palettes = sorted(palettes_dir.glob("ide_palette_*.json"))
    if not ide_palettes:
        raise SystemExit("No IDE palette files found. Generate first.")

    contributes = []
    for p in ide_palettes:
        pal = _load_palette(p)
        if "hue_family" not in pal:
            accent_hex = _role_map(pal).get("accent_primary")
            if accent_hex:
                hue = hex_to_hsl(accent_hex)[0]
                if hue < 15 or hue >= 345:
                    pal["hue_family"] = "red"
                elif hue < 40:
                    pal["hue_family"] = "orange"
                elif hue < 60:
                    pal["hue_family"] = "amber"
                elif hue < 160:
                    pal["hue_family"] = "green"
                elif hue < 200:
                    pal["hue_family"] = "cyan"
                elif hue < 235:
                    pal["hue_family"] = "blue"
                elif hue < 265:
                    pal["hue_family"] = "indigo"
                elif hue < 295:
                    pal["hue_family"] = "purple"
                else:
                    pal["hue_family"] = "magenta"
        file_name = f"{p.stem}.json"
        theme_data = _theme_json(pal)
        (themes_dir / file_name).write_text(json.dumps(theme_data, indent=2), encoding="utf-8")
        ui_theme = "vs" if theme_data.get("type") == "light" else "vs-dark"
        contributes.append({"label": theme_data["name"], "uiTheme": ui_theme, "path": f"./themes/{file_name}"})

    current_package = {}
    package_path = ext_dir / "package.json"
    if package_path.exists():
        current_package = json.loads(package_path.read_text(encoding="utf-8"))
    next_version = _bump_patch_version(str(current_package.get("version", "0.0.0")))

    package_json = {
        "name": "robross-ide-palettes",
        "displayName": "RobRoss IDE Palettes",
        "description": "Generated IDE themes from RobRoss Palette Engine",
        "version": next_version,
        "publisher": "local",
        "engines": {"vscode": "^1.85.0"},
        "categories": ["Themes"],
        "contributes": {"themes": contributes},
    }
    package_path.write_text(json.dumps(package_json, indent=2), encoding="utf-8")
    (ext_dir / "README.md").write_text(
        "\n".join(
            [
                "# RobRoss IDE Themes",
                "",
                "Generated from `outputs/palettes/ide_palette_*.json`.",
                "",
                "## Build VSIX locally",
                "",
                "1. `npm i -g @vscode/vsce`",
                "2. `cd vscode-themes`",
                "3. `vsce package`",
                "4. In Cursor/VSCode: Extensions -> ... -> Install from VSIX",
                "",
                "## Regenerate themes",
                "",
                "- From project root: `python scripts/export_vscode_themes.py`",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Generated {len(contributes)} themes in {themes_dir}")
    print(f"Extension version: {next_version}")

    if package_vsix:
        print("Packaging VSIX...")
        npx_cmd = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx_cmd:
            raise RuntimeError("Could not find npx in PATH. Install Node.js/npm to package VSIX.")
        subprocess.run([npx_cmd, "@vscode/vsce", "package"], cwd=ext_dir, check=True)


if __name__ == "__main__":
    main()
