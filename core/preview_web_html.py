"""Browser gallery for website palettes (mock landing strip)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from core.pathways.web import describe_harmony


def _role_colors(palette: dict[str, Any]) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            m[str(role)] = str(hx)
    return m


def _landing_mock(roles: dict[str, str]) -> str:
    bg = roles.get("background", "#060607")
    fg = roles.get("foreground", "#fafafa")
    muted = roles.get("muted", "#a8a8a8")
    acc = roles.get("accent_primary", "#edd750")
    surf = roles.get("surface", "#0a0b0d")
    return f"""<div style="background:{html.escape(bg)};color:{html.escape(fg)};border-radius:10px;padding:20px 22px;font-family:system-ui,sans-serif">
  <p style="margin:0 0 6px;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:{html.escape(muted)}">Studio</p>
  <h3 style="margin:0 0 10px;font-size:1.35rem;font-weight:600">Hero headline</h3>
  <p style="margin:0 0 14px;font-size:0.9rem;color:{html.escape(muted)};max-width:28em">Supporting line — readability check on muted token.</p>
  <a href="#" style="display:inline-block;padding:10px 18px;border-radius:6px;background:{html.escape(acc)};color:{html.escape(bg)};text-decoration:none;font-weight:600;font-size:0.85rem">Primary CTA</a>
  <div style="margin-top:14px;height:8px;border-radius:4px;background:{html.escape(surf)}"></div>
</div>"""


def build_web_preview_page(palettes: list[dict[str, Any]], out_path: Path, title: str = "Rob Ross — web palettes") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for pal in palettes:
        pid = html.escape(str(pal.get("id", "palette")))
        site = html.escape(str(pal.get("site", "generic")))
        mode = html.escape(str(pal.get("harmony_mode", "?")))
        harm_note = html.escape(describe_harmony(str(pal.get("harmony_mode", "analogous"))))
        roles = _role_colors(pal)
        sw = pal.get("harmony_swatches") or []
        swatch_row = "".join(
            f'<span style="display:inline-block;width:36px;height:36px;border-radius:6px;background:{html.escape(h)};border:1px solid rgba(255,255,255,0.12)" title="{html.escape(h)}"></span>'
            for h in sw
        )
        conflicts = pal.get("conflicts_flagged") or []
        warn = (
            f'<p class="warn">Contrast flags: {html.escape(", ".join(conflicts))}</p>'
            if conflicts
            else ""
        )
        mock = _landing_mock(roles)
        export_hint = html.escape(
            f"python cli.py web export {pal.get('id', '')} --site {pal.get('site', 'generic')}"
        )
        cards.append(
            f"""<article class="card">
  <header><h2>{pid}</h2><p class="meta">site: {site} · harmony: {mode}</p></header>
  <p class="harm">{harm_note}</p>
  <div class="swatches">{swatch_row}</div>
  {mock}
  {warn}
  <footer><code>{export_hint}</code></footer>
</article>"""
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{ font-family: system-ui, sans-serif; background: #0f0f12; color: #e4e4e7; }}
    body {{ margin: 0; padding: 24px; max-width: 1100px; margin-inline: auto; }}
    h1 {{ font-size: 1.25rem; }}
    .hint {{ color: #a1a1aa; font-size: 0.9rem; margin-bottom: 20px; }}
    .grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }}
    .card {{ background: #18181b; border-radius: 12px; padding: 16px; border: 1px solid #27272a; }}
    .meta {{ color: #71717a; font-size: 0.8rem; margin: 0; }}
    .harm {{ font-size: 0.82rem; color: #d4d4d8; margin: 8px 0; }}
    .swatches {{ display: flex; gap: 6px; margin: 10px 0 14px; flex-wrap: wrap; }}
    .warn {{ color: #fbbf24; font-size: 0.78rem; }}
    footer code {{ font-size: 0.68rem; color: #a1a1aa; word-break: break-all; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="hint">Coolors-style harmonies → semantic roles → site CSS via <code>web export</code>. Reno uses brand-lock (accents only).</p>
  <div class="grid">{"".join(cards)}</div>
</body>
</html>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def load_web_palettes_from_dir(palette_dir: Path, site: str | None = None) -> list[dict[str, Any]]:
    site_key = (site or "").strip().lower()
    paths = sorted(palette_dir.glob("web_*_palette_*.json"))
    out: list[dict[str, Any]] = []
    for p in paths:
        pal = json.loads(p.read_text(encoding="utf-8"))
        if site_key and pal.get("site") != site_key:
            continue
        out.append(pal)
    return out
