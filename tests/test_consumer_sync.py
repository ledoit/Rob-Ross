"""Consumer sync tests."""

from __future__ import annotations

import json
from pathlib import Path

from core.export.consumer_sync import ide_palette_to_site_theme, render_typescript_paid, sync_consumer


def _minimal_palette(**extra: object) -> dict:
    base = {
        "id": "ide_palette_01",
        "context": "ide",
        "style_archetype": "night_siren",
        "is_light": False,
        "colors": [
            {"role": "background", "hex": "#0D1112"},
            {"role": "foreground", "hex": "#F6F8F8"},
            {"role": "surface", "hex": "#1A2428"},
            {"role": "border", "hex": "#3E637E"},
            {"role": "muted", "hex": "#3E637E"},
            {"role": "accent_primary", "hex": "#46DCF6"},
            {"role": "accent_secondary", "hex": "#387FF0"},
            {"role": "syntax_1", "hex": "#46DCF6"},
            {"role": "syntax_2", "hex": "#387FF0"},
            {"role": "syntax_3", "hex": "#5CE0C0"},
            {"role": "syntax_4", "hex": "#F0A848"},
            {"role": "syntax_5", "hex": "#F06080"},
        ],
    }
    base.update(extra)
    return base


def test_ide_palette_to_site_theme_slug() -> None:
    theme = ide_palette_to_site_theme(_minimal_palette())
    assert theme["id"] == "night-siren"
    assert theme["mode"] == "dark"
    assert len(theme["blockColors"]) == 5


def test_render_typescript_paid_no_bonfire() -> None:
    themes = [ide_palette_to_site_theme(_minimal_palette())]
    out = render_typescript_paid(themes, source_note="test")
    assert "bonfire-gold" not in out
    assert "night-siren" in out


def test_sync_consumer_writes_file(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (palette_dir / "ide_palette_01.json").write_text(json.dumps(_minimal_palette()), encoding="utf-8")
    target = tmp_path / "site" / "themes.ts"
    (gdir / "web_consumers.json").write_text(
        json.dumps(
            {
                "consumers": {
                    "demo": {
                        "label": "Demo",
                        "format": "typescript_paid",
                        "path": "site/themes.ts",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = sync_consumer(tmp_path, "demo", roster_only=False)
    assert target.is_file()
    assert result["theme_count"] == 1
