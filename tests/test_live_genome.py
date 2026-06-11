"""Live genome layer tests."""

from __future__ import annotations

import json
from pathlib import Path

from core.ide_iteration import record_draft
from core.layout import registry_dir
from core.live_genome import apply_live_genome, build_roster_live_layer, extract_palette_features
from core.roster import roster_add


def _palette(pid: str, style: str, accent: str) -> dict:
    return {
        "id": pid,
        "context": "ide",
        "style_archetype": style,
        "is_light": False,
        "hue_family": "blue",
        "colors": [
            {"role": "background", "hex": "#0D1112"},
            {"role": "foreground", "hex": "#F6F8F8"},
            {"role": "accent_primary", "hex": accent},
            {"role": "accent_secondary", "hex": "#387FF0"},
            {"role": "syntax_1", "hex": accent},
        ],
    }


def test_extract_palette_features() -> None:
    feat = extract_palette_features(_palette("ide_palette_01", "night_siren", "#46DCF6"))
    assert feat["style_archetype"] == "night_siren"
    assert feat["accent_hue"] > 0


def test_build_roster_live_layer_relationships(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    for pid, accent in (("ide_palette_01", "#46DCF6"), ("ide_palette_02", "#387FF0")):
        (palette_dir / f"{pid}.json").write_text(json.dumps(_palette(pid, "night_siren", accent)), encoding="utf-8")
        roster_add(reg, palette_dir, pid)
    layer = build_roster_live_layer(tmp_path)
    assert layer is not None
    assert len(layer["relationships"]) == 1
    assert layer["synthesis"]["accent_hue_center"] is not None


def test_apply_live_genome_merges_without_persisting(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (palette_dir / "ide_palette_12.json").write_text(
        json.dumps(_palette("ide_palette_12", "lemon_paper", "#F0E040")),
        encoding="utf-8",
    )
    roster_add(reg, palette_dir, "ide_palette_12")
    record_draft(tmp_path, "ide_palette_12", "lemon", derived_from=None)
    base = {"version": "1.1.0", "style_archetypes": {"ide": ["dracula_punch"]}}
    merged = apply_live_genome(base, tmp_path)
    assert "roster_live" in merged
    assert "lemon_paper" in merged["style_archetypes"]["ide"]
    assert not (tmp_path / "genome" / "genome_v1.json").exists()
