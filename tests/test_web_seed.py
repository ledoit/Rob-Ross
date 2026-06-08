"""Generate from saved palette seed."""

from __future__ import annotations

import json
from pathlib import Path

from core.roster import roster_add
from core.studio_web import apply_palette_seed_to_genome, palette_to_generate_params
from core.web_session import run_web_quick


def test_palette_to_generate_params() -> None:
    pal = {
        "id": "web_photoport_palette_01",
        "site": "photoport",
        "harmony_mode": "complementary",
        "user_prompt": "classy",
        "generation_controls": {"chromatic_variety": 0.5, "prompt_adherence": 0.8},
        "colors": [
            {"role": "accent_secondary", "hex": "#ea9947"},
            {"role": "background", "hex": "#141719"},
        ],
    }
    p = palette_to_generate_params(pal)
    assert p["site"] == "photoport"
    assert p["harmony"] == "complementary"
    assert p["variety"] == 0.5
    assert p["accent_hue_center"] == 30


def test_list_saved_includes_disk_without_roster(tmp_path: Path) -> None:
    from core.studio_web import list_saved_web_palettes

    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    run_web_quick(tmp_path, "classy", count=1, site="photoport")
    rows = list_saved_web_palettes(gdir, palette_dir)
    assert len(rows) == 1
    assert rows[0]["id"] == "web_photoport_palette_01"
    assert rows[0]["pinned"] is False


def test_run_web_quick_seed_from(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(
        json.dumps({"version": "1.1.0", "prompt_session": {}}),
        encoding="utf-8",
    )
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)

    run_web_quick(tmp_path, "classy professional", count=1, site="photoport", harmony="complementary")
    pid = "web_photoport_palette_01"
    roster_add(gdir, palette_dir, pid)

    result = run_web_quick(
        tmp_path,
        "classy professional refined",
        count=2,
        site="photoport",
        seed_from=pid,
        variety=0.4,
    )
    assert result["seed_from"] == pid
    assert (palette_dir / "web_photoport_palette_01.json").is_file()
    assert (palette_dir / "web_photoport_palette_02.json").is_file()
