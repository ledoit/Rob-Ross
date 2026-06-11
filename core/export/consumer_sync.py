"""Push genome palettes into downstream website consumers (TypeScript, CSS, etc.)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.ide_iteration import kept_palette_ids, ship_palette_ids
from core.ide_schema import enrich_legacy_palette, palette_meta, resolve_branded_name, strip_theme_prefix
from core.math_engine import hex_to_hsl, hsl_to_hex
from core.roster import load_roster

# Reuse VS Code chrome tuning for bar/panel/selection in site tokens.
STYLE_CHROME_PROFILES: dict[str, dict[str, Any]] = {
    "dracula_punch": {"bar_lift": 2, "selection_alpha": "66", "focus": "accent"},
    "fjord_hammer": {"bar_lift": 4, "selection_alpha": "4A", "focus": "accent"},
    "alpenglow_paper": {"bar_lift": 4, "selection_alpha": "3C", "focus": "muted"},
    "kimbie_warm": {"bar_lift": 3, "selection_alpha": "5A", "focus": "accent2"},
    "ion_storm": {"bar_lift": 0, "selection_alpha": "7E", "focus": "accent"},
    "forest_canopy": {"bar_lift": 2, "selection_alpha": "56", "focus": "accent2"},
    "void_forge": {"bar_lift": 0, "selection_alpha": "72", "focus": "accent2"},
    "lemon_paper": {"bar_lift": 3, "selection_alpha": "40", "focus": "accent"},
    "lemon_cream": {"bar_lift": 2, "selection_alpha": "50", "focus": "accent", "selection": "accent2"},
    "candy_voltage": {"bar_lift": 2, "selection_alpha": "7A", "focus": "accent"},
    "night_siren": {"bar_lift": 0, "selection_alpha": "7A", "focus": "accent2"},
    "high_contrast_signal": {"bar_lift": 0, "selection_alpha": "88", "focus": "accent"},
}

CONSUMERS_FILENAME = "web_consumers.json"


def _role_map(palette: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            out[str(role)] = str(hx)
    return out


def _tone(hex_color: str, l_shift: float = 0.0) -> str:
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, s, max(0, min(100, l + l_shift)))


def _slug(style_archetype: str) -> str:
    return style_archetype.replace("_", "-")


def ide_palette_to_site_theme(palette: dict[str, Any]) -> dict[str, Any]:
    """Map an IDE palette JSON document to a generic site theme record."""
    palette = enrich_legacy_palette(palette)
    roles = _role_map(palette)
    meta = palette_meta(palette)
    style = meta["style_archetype"]
    chrome = STYLE_CHROME_PROFILES.get(style, {"bar_lift": 2, "selection_alpha": "55", "focus": "accent"})

    bg = roles.get("background", "#1E1E2E")
    fg = roles.get("foreground", "#CDD6F4")
    surface = roles.get("surface", bg)
    muted = roles.get("muted", "#6C7086")
    accent1 = roles.get("accent_primary", "#89B4FA")
    accent2 = roles.get("accent_secondary", "#CBA6F7")
    syntax = [roles.get(f"syntax_{i}") for i in range(1, 7)]
    syntax = [c for c in syntax if c]
    while len(syntax) < 5:
        syntax.append(accent1 if len(syntax) % 2 == 0 else accent2)

    focus = accent1 if chrome["focus"] == "accent" else accent2 if chrome["focus"] == "accent2" else muted
    selection_base = accent2 if chrome.get("selection") == "accent2" else accent1
    panel = _tone(surface, l_shift=chrome["bar_lift"])
    bar = _tone(bg, l_shift=max(0, chrome["bar_lift"] - 1))
    label = strip_theme_prefix(resolve_branded_name(palette))

    return {
        "id": _slug(style),
        "palette_id": palette.get("id", ""),
        "label": label,
        "mode": meta["theme_mode"],
        "bg": bg,
        "fg": fg,
        "surface": surface,
        "bar": bar,
        "panel": panel,
        "border": roles.get("border", muted),
        "accent": accent1,
        "accentHover": accent2,
        "focus": focus,
        "muted": muted,
        "selection": f"{selection_base}{chrome['selection_alpha']}",
        "blockColors": syntax[:5],
    }


def consumers_path(genome_dir: Path) -> Path:
    return genome_dir / CONSUMERS_FILENAME


def load_consumers(genome_dir: Path) -> dict[str, Any]:
    p = consumers_path(genome_dir)
    if not p.is_file():
        return {"consumers": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("consumers", {})
    return data


def resolve_palette_ids(root: Path, *, roster_only: bool = True, extra_ids: list[str] | None = None) -> list[str]:
    """IDE palette ids to sync — kept roster + draft, or every ide_palette_* on disk."""
    gdir = root / "genome"
    palette_dir = root / "outputs" / "palettes"
    if roster_only:
        ids = ship_palette_ids(root)
        if ids:
            return sorted(ids)
        kept = kept_palette_ids(gdir)
        if kept:
            return sorted(kept)
    stems = sorted(p.stem for p in palette_dir.glob("ide_palette_*.json"))
    if extra_ids:
        stems = sorted(set(stems) | {x.replace(".json", "") for x in extra_ids})
    return [s for s in stems if s != "ide_palette_08"]


def load_ide_palettes(root: Path, palette_ids: list[str]) -> list[dict[str, Any]]:
    palette_dir = root / "outputs" / "palettes"
    out: list[dict[str, Any]] = []
    for pid in palette_ids:
        path = palette_dir / f"{pid}.json"
        if not path.is_file():
            continue
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def _ts_string(s: str) -> str:
    return json.dumps(s)


def render_typescript_paid(themes: list[dict[str, Any]], *, source_note: str) -> str:
    ids = [t["id"] for t in themes]
    id_union = "\n  | ".join(f'"{i}"' for i in ids)
    blocks: list[str] = []
    for t in themes:
        blocks.append(
            "  {\n"
            f'    id: {_ts_string(t["id"])},\n'
            f'    label: {_ts_string(t["label"])},\n'
            f'    mode: {_ts_string(t["mode"])},\n'
            f'    bg: {_ts_string(t["bg"])},\n'
            f'    fg: {_ts_string(t["fg"])},\n'
            f'    surface: {_ts_string(t["surface"])},\n'
            f'    bar: {_ts_string(t["bar"])},\n'
            f'    panel: {_ts_string(t["panel"])},\n'
            f'    border: {_ts_string(t["border"])},\n'
            f'    accent: {_ts_string(t["accent"])},\n'
            f'    accentHover: {_ts_string(t["accentHover"])},\n'
            f'    focus: {_ts_string(t["focus"])},\n'
            f'    muted: {_ts_string(t["muted"])},\n'
            f'    selection: {_ts_string(t["selection"])},\n'
            f'    blockColors: [{", ".join(_ts_string(c) for c in t["blockColors"])}],\n'
            "  }"
        )
    default_id = ids[-1] if ids else "night-siren"
    themes_body = ",\n".join(blocks)
    return f"""/** {source_note} */

export type ThemeId =
  | {id_union};

export type ThemeMode = "light" | "dark";

export type PaidTheme = {{
  id: ThemeId;
  label: string;
  mode: ThemeMode;
  bg: string;
  fg: string;
  surface: string;
  bar: string;
  panel: string;
  border: string;
  accent: string;
  accentHover: string;
  focus: string;
  muted: string;
  selection: string;
  blockColors: [string, string, string, string, string];
}};

export const THEMES: PaidTheme[] = [
{themes_body}
];

export const DEFAULT_THEME_ID: ThemeId = {_ts_string(default_id)};

export function getTheme(id: ThemeId): PaidTheme {{
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}}

export function nextThemeId(current: ThemeId): ThemeId {{
  const idx = THEMES.findIndex((t) => t.id === current);
  return THEMES[(idx + 1) % THEMES.length].id;
}}

export function applyTheme(theme: PaidTheme) {{
  const root = document.documentElement;
  root.dataset.theme = theme.id;
  root.dataset.mode = theme.mode;
  root.style.setProperty("--paid-bg", theme.bg);
  root.style.setProperty("--paid-fg", theme.fg);
  root.style.setProperty("--paid-surface", theme.surface);
  root.style.setProperty("--paid-bar", theme.bar);
  root.style.setProperty("--paid-panel", theme.panel);
  root.style.setProperty("--paid-border", theme.border);
  root.style.setProperty("--paid-accent", theme.accent);
  root.style.setProperty("--paid-accent-hover", theme.accentHover);
  root.style.setProperty("--paid-focus", theme.focus);
  root.style.setProperty("--paid-muted", theme.muted);
  root.style.setProperty("--paid-selection", theme.selection);
  theme.blockColors.forEach((c, i) => {{
    root.style.setProperty(`--paid-block-${{i}}`, c);
  }});
}}
"""


def sync_consumer(
    root: Path,
    consumer_id: str,
    *,
    roster_only: bool = True,
    palette_ids: list[str] | None = None,
) -> dict[str, Any]:
    gdir = root / "genome"
    registry = load_consumers(gdir)
    spec = (registry.get("consumers") or {}).get(consumer_id)
    if not spec:
        known = ", ".join(sorted((registry.get("consumers") or {}).keys())) or "(none)"
        raise KeyError(f"Unknown consumer {consumer_id!r}. Registered: {known}")

    rel = str(spec["path"])
    target = (root / rel).resolve()
    fmt = str(spec.get("format", "typescript_paid"))
    ids = palette_ids or resolve_palette_ids(root, roster_only=roster_only)
    palettes = load_ide_palettes(root, ids)
    if not palettes:
        raise FileNotFoundError("No IDE palettes matched for sync")

    themes = [ide_palette_to_site_theme(p) for p in palettes]
    # One theme per style slug (latest palette wins).
    by_slug: dict[str, dict[str, Any]] = {}
    for t in themes:
        by_slug[t["id"]] = t
    themes = list(by_slug.values())
    themes.sort(key=lambda t: t["palette_id"])

    source_note = spec.get("source_note") or f"Rob Ross — synced from {root.name}"
    if fmt == "typescript_paid":
        body = render_typescript_paid(themes, source_note=source_note)
    else:
        raise ValueError(f"Unsupported consumer format: {fmt}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return {
        "consumer": consumer_id,
        "path": str(target),
        "palette_ids": [p.get("id") for p in palettes],
        "theme_count": len(themes),
    }
