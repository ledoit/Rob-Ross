"""Emit CSS custom properties for marketing sites from web palette JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.pathways.web_sites import get_site_profile, normalize_site_id


def _role_map(palette: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            out[str(role)] = str(hx)
    return out


def _reno_grey_ladder(roles: dict[str, str]) -> dict[str, str]:
    """Optional grey ramp derived from background (brand-lock friendly)."""
    bg = roles.get("background", "#060607")
    return {
        "--palette-black": "#000000",
        "--palette-white": roles.get("foreground", "#ffffff"),
        "--palette-dark-900": bg,
        "--palette-dark-800": roles.get("surface", "#0a0b0d"),
        "--palette-dark-700": roles.get("elevated", roles.get("surface", "#101216")),
        "--palette-grey-18": roles.get("border", "#2e2e2e"),
        "--palette-border-soft": "rgba(255, 255, 255, 0.16)",
    }


def palette_to_css(
    palette: dict[str, Any],
    *,
    site: str | None = None,
    scope: str = ":root",
) -> str:
    """Build a CSS partial with semantic site tokens."""
    site_key = normalize_site_id(site or palette.get("site"))
    profile = get_site_profile(site_key)
    prefix = str(profile.get("export_prefix", "web"))
    roles = _role_map(palette)
    lines = [
        f"/* Rob Ross web export — {palette.get('id', 'palette')} — site: {site_key} */",
        f"/* Harmony: {palette.get('harmony_mode', '?')} — {palette.get('palette_rationale', '')[:120]} */",
        "",
        scope + " {",
    ]

    if site_key == "reno":
        for k, v in _reno_grey_ladder(roles).items():
            lines.append(f"  {k}: {v};")
        lines.append(f"  --site-surface-bg: {roles.get('background', '#060607')};")
        lines.append(f"  --site-text: var(--palette-white);")
        lines.append(f"  --site-muted: {roles.get('muted', '#cdcdcd')};")
        lines.append(f"  --site-accent-primary: {roles.get('accent_primary', '#edd750')};")
        lines.append(f"  --site-accent-secondary: {roles.get('accent_secondary', roles.get('accent_primary', '#edd750'))};")
    else:
        lines.append(f"  --{prefix}-background: {roles.get('background', '#0f0f12')};")
        lines.append(f"  --{prefix}-surface: {roles.get('surface', '#18181b')};")
        lines.append(f"  --{prefix}-foreground: {roles.get('foreground', '#fafafa')};")
        lines.append(f"  --{prefix}-muted: {roles.get('muted', '#a1a1aa')};")
        lines.append(f"  --{prefix}-border: {roles.get('border', '#27272a')};")
        lines.append(f"  --{prefix}-accent-primary: {roles.get('accent_primary', '#3b82f6')};")
        lines.append(f"  --{prefix}-accent-secondary: {roles.get('accent_secondary', roles.get('accent_primary', '#3b82f6'))};")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def export_palette_file(
    palette_path: Path,
    out_dir: Path,
    *,
    site: str | None = None,
) -> Path:
    palette = json.loads(palette_path.read_text(encoding="utf-8"))
    site_key = normalize_site_id(site or palette.get("site"))
    out_dir.mkdir(parents=True, exist_ok=True)
    css_path = out_dir / site_key / f"{palette.get('id', palette_path.stem)}.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(palette_to_css(palette, site=site_key), encoding="utf-8")
    json_path = css_path.with_suffix(".tokens.json")
    json_path.write_text(
        json.dumps({"site": site_key, "roles": _role_map(palette), "palette_id": palette.get("id")}, indent=2),
        encoding="utf-8",
    )
    return css_path


def export_all_web_palettes(palette_dir: Path, out_dir: Path) -> list[Path]:
    written: list[Path] = []
    for p in sorted(palette_dir.glob("web_*_palette_*.json")):
        written.append(export_palette_file(p, out_dir))
    return written
