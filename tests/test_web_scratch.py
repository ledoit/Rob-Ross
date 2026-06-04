"""Web scratch replace — unsaved palettes dropped on regenerate."""

from __future__ import annotations

import json
from pathlib import Path

from core.roster import roster_add
from core.web_session import run_web_quick, scratch_unsaved_web_palettes


def test_scratch_removes_unsaved_keeps_roster(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)

    run_web_quick(tmp_path, "first", count=1, site="photoport")
    pid = "web_photoport_palette_01"
    assert (palette_dir / f"{pid}.json").is_file()

    roster_add(gdir, palette_dir, pid, prompt="keep me")
    (palette_dir / "web_photoport_palette_02.json").write_text(
        json.dumps({"id": "web_photoport_palette_02", "site": "photoport", "colors": []}),
        encoding="utf-8",
    )

    removed, kept = scratch_unsaved_web_palettes(palette_dir, gdir, "photoport")
    assert pid in kept
    assert "web_photoport_palette_02" in removed
    assert not (palette_dir / "web_photoport_palette_02.json").exists()
    assert (palette_dir / f"{pid}.json").exists()


def test_run_web_quick_replaces_scratch(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)

    run_web_quick(tmp_path, "a", count=2, site="reno")
    assert (palette_dir / "web_reno_palette_01.json").is_file()
    assert (palette_dir / "web_reno_palette_02.json").is_file()

    result = run_web_quick(tmp_path, "b", count=1, site="reno")
    assert len(result["scratch_removed"]) == 2
    assert (palette_dir / "web_reno_palette_01.json").is_file()
    assert not (palette_dir / "web_reno_palette_02.json").exists()
