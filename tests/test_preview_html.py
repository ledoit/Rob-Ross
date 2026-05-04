from pathlib import Path

from core.preview_html import _explain_taste_context, build_preview_page


def test_explain_taste_context_two_parts():
    s = _explain_taste_context("forest_console:ion_storm")
    assert "taste mood" in s
    assert "ion_storm" in s
    assert "omitted" in s or "Theme mode" in s


def test_build_preview_writes_html(tmp_path: Path):
    palettes = [
        {
            "id": "ide_palette_01",
            "taste_context": "x:y:dark",
            "user_prompt": "black and yellow",
            "colors": [
                {"role": "background", "hex": "#0a0a0c"},
                {"role": "foreground", "hex": "#f4f4f5"},
                {"role": "muted", "hex": "#71717a"},
                {"role": "accent_primary", "hex": "#eab308"},
                {"role": "accent_secondary", "hex": "#ca8a04"},
                {"role": "syntax_1", "hex": "#86efac"},
                {"role": "syntax_2", "hex": "#fcd34d"},
                {"role": "syntax_3", "hex": "#c084fc"},
                {"role": "syntax_4", "hex": "#67e8f9"},
                {"role": "syntax_5", "hex": "#93c5fd"},
                {"role": "syntax_6", "hex": "#f87171"},
            ],
        }
    ]
    out = tmp_path / "index.html"
    build_preview_page(palettes, out)
    text = out.read_text(encoding="utf-8")
    assert "ide_palette_01" in text
    assert "#0a0a0c" in text
    assert "black and yellow" in text
    assert "Rob Ross" in text
