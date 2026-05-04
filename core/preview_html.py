"""Build a static HTML page to eyeball IDE palettes before picking roster keepers."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _role_colors(palette: dict[str, Any]) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            m[str(role)] = str(hx)
    return m


def _snippet_html(roles: dict[str, str]) -> str:
    """Fake editor line using palette roles (fallbacks if missing)."""
    bg = roles.get("background", "#1a1a1e")
    fg = roles.get("foreground", "#e4e4e7")
    kw = roles.get("syntax_3", roles.get("accent_primary", "#c084fc"))
    fn = roles.get("syntax_4", roles.get("accent_secondary", "#67e8f9"))
    st = roles.get("syntax_1", "#86efac")
    num = roles.get("syntax_2", "#fcd34d")
    ty = roles.get("syntax_5", "#93c5fd")
    cm = roles.get("muted", "#71717a")
    inv = roles.get("syntax_6", "#f87171")

    def span(style: str, text: str) -> str:
        return f'<span style="{html.escape(style)}">{html.escape(text)}</span>'

    line1 = (
        span(f"color:{cm};font-style:italic", "// preview — RobRoss")
        + span(f"color:{fg}", "\n")
    )
    line2 = (
        span(f"color:{kw}", "import ")
        + span(f"color:{ty}", "React")
        + span(f"color:{fg}", " ")
        + span(f"color:{kw}", "from ")
        + span(f"color:{st}", "'react'")
        + span(f"color:{fg}", ";\n")
    )
    line3 = (
        span(f"color:{kw}", "function ")
        + span(f"color:{fn}", "usePalette")
        + span(f"color:{fg}", "() {\n")
    )
    line4 = (
        "  "
        + span(f"color:{kw}", "const ")
        + span(f"color:{fg}", "n ")
        + span(f"color:{fg}", "= ")
        + span(f"color:{num}", "42")
        + span(f"color:{fg}", ";\n")
    )
    line5 = (
        "  "
        + span(f"color:{kw}", "return ")
        + span(f"color:{st}", "`theme-${n}`")
        + span(f"color:{fg}", ";\n")
    )
    line6 = span(f"color:{inv}", "typo!!!") + span(f"color:{fg}", "\n")
    line7 = span(f"color:{fg}", "}\n")

    inner = line1 + line2 + line3 + line4 + line5 + line6 + line7
    return f'<pre style="margin:0;padding:12px 14px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.45;background:{html.escape(bg)};color:{html.escape(fg)};border-radius:8px;overflow:auto">{inner}</pre>'


def build_preview_page(
    palettes: list[dict[str, Any]],
    out_path: Path,
    title: str = "RobRoss palette preview",
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for pal in palettes:
        pid = html.escape(str(pal.get("id", "palette")))
        tc = html.escape(str(pal.get("taste_context", "")))
        up = pal.get("user_prompt")
        prompt_line = (
            f'<p class="prompt">{html.escape(str(up))}</p>' if up else ""
        )
        roles = _role_colors(pal)
        snippet = _snippet_html(roles)
        roster_hint = html.escape(f'python cli.py roster add {pal.get("id", "")} --prompt "..."')
        cards.append(
            f"""<article class="card">
  <header><h2>{pid}</h2><p class="meta">{tc}</p>{prompt_line}</header>
  {snippet}
  <footer><code>{roster_hint}</code></footer>
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
    body {{ margin: 0; padding: 24px; max-width: 1200px; margin-inline: auto; }}
    h1 {{ font-size: 1.25rem; margin-bottom: 8px; }}
    .hint {{ color: #a1a1aa; font-size: 0.9rem; margin-bottom: 24px; }}
    .grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }}
    .card {{ background: #18181b; border-radius: 12px; padding: 16px; border: 1px solid #27272a; }}
    .card header h2 {{ margin: 0 0 4px; font-size: 1rem; }}
    .meta {{ margin: 0 0 8px; color: #a1a1aa; font-size: 0.8rem; word-break: break-all; }}
    .prompt {{ margin: 0 0 10px; color: #d4d4d8; font-size: 0.85rem; }}
    .card footer {{ margin-top: 12px; }}
    .card footer code {{ font-size: 0.7rem; color: #71717a; word-break: break-all; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="hint">Compare mock editor chrome below, then add keepers with <code>python cli.py roster add …</code></p>
  <div class="grid">
{"".join(cards)}
  </div>
</body>
</html>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def load_ide_palettes_from_dir(palette_dir: Path, ids: list[str] | None) -> list[dict[str, Any]]:
    if ids:
        out: list[dict[str, Any]] = []
        for stem in ids:
            p = palette_dir / f"{stem.replace('.json', '')}.json"
            if p.is_file():
                out.append(json.loads(p.read_text(encoding="utf-8")))
        return out
    paths = sorted(palette_dir.glob("ide_palette_*.json"))
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]
