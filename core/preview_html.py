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
        span(f"color:{cm};font-style:italic", "// preview — Rob Ross")
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


def _explain_taste_context(tc: str) -> str:
    """Human-readable caption for internal taste_context string (always same prose shape)."""
    raw = (tc or "").strip()
    if not raw:
        return "Recipe line: (missing). This file has no taste_context; try regenerating."
    parts = [p.strip() for p in raw.split(":") if p.strip()]
    suffix = " This is not your export list — only how the generator labeled this variant."
    if len(parts) >= 3:
        return (
            f"Recipe line: taste mood “{html.escape(parts[0])}”, style archetype “{html.escape(parts[1])}”, "
            f"light/dark “{html.escape(parts[2])}”.{suffix}"
        )
    if len(parts) == 2:
        return (
            f"Recipe line: taste mood “{html.escape(parts[0])}”, style archetype “{html.escape(parts[1])}”. "
            f"Theme mode was omitted in the label (older or partial write).{suffix}"
        )
    return f"Recipe line: single tag “{html.escape(parts[0])}”.{suffix}"


def build_preview_page(
    palettes: list[dict[str, Any]],
    out_path: Path,
    title: str = "Rob Ross palette preview",
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for pal in palettes:
        pid = html.escape(str(pal.get("id", "palette")))
        tc_raw = str(pal.get("taste_context", ""))
        tc_expl = _explain_taste_context(tc_raw)
        gc = pal.get("generation_controls") or {}
        if gc.get("chromatic_variety") is not None and gc.get("prompt_adherence") is not None:
            gc_body = (
                f'variety {html.escape(str(gc.get("chromatic_variety")))}, '
                f'prompt adherence {html.escape(str(gc.get("prompt_adherence")))}'
            )
        else:
            gc_body = (
                "not stored on this JSON. Common when this slot was reused from disk before a full "
                "<span class='mono'>quick</span> regen — run "
                "<span class='mono'>python cli.py quick \"…\"</span> again so every slot is rewritten."
            )
        gc_line = f'<p class="label">Generation controls</p><p class="gc">{gc_body}</p>'
        up = pal.get("user_prompt")
        if up:
            prompt_body = html.escape(str(up))
        else:
            prompt_body = (
                "<span class='muted2'>Not stored. Only slots that were actually regenerated in your last "
                "<span class='mono'>quick</span> run get a brief; delete stale "
                "<span class='mono'>ide_palette_*.json</span> "
                "or run <span class='mono'>quick</span> again so all files match.</span>"
            )
        prompt_line = f'<p class="label">Your brief</p><p class="prompt">{prompt_body}</p>'
        roles = _role_colors(pal)
        snippet = _snippet_html(roles)
        finalize_hint = html.escape(f'python cli.py roster add {pal.get("id", "")} --prompt "your brief"')
        shortlist_hint = html.escape(f'python cli.py roster shortlist add {pal.get("id", "")} --prompt "your brief"')
        cards.append(
            f"""<article class="card">
  <header><h2>{pid}</h2></header>
  <p class="label">Internal recipe (not export roster)</p>
  <p class="meta">{tc_expl}</p>
  {gc_line}
  {prompt_line}
  {snippet}
  <footer>
    <p class="label">Final pick (goes to VS Code export list)</p>
    <code>{finalize_hint}</code>
    <p class="label">Shortlist (best of batch — biases the next quick regen only)</p>
    <code>{shortlist_hint}</code>
  </footer>
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
    .label {{ margin: 10px 0 4px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: #a1a1aa; }}
    .meta {{ margin: 0 0 8px; color: #d4d4d8; font-size: 0.82rem; line-height: 1.4; }}
    .gc {{ margin: 0 0 8px; color: #a3a3a3; font-size: 0.78rem; }}
    .prompt {{ margin: 0 0 10px; color: #fafafa; font-size: 0.88rem; }}
    .muted2 {{ color: #71717a; }}
    .mono {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85em; }}
    .card footer {{ margin-top: 14px; }}
    .card footer > code {{ display: block; font-size: 0.68rem; color: #a1a1aa; word-break: break-all; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="hint">Each card shows one generated <code>ide_palette_XX.json</code>. The “recipe” line is an internal label (taste + archetype + theme mode), not which themes you chose for export.</p>
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
