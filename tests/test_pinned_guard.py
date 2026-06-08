"""Pinned palettes must not be overwritten by tweak/reroll."""

from __future__ import annotations

import json
from pathlib import Path

from core.roster import roster_add
from core.studio_web import is_web_palette_pinned, load_palette_file, tweak_palette
from core.web_session import run_web_quick


def test_reroll_pinned_writes_new_scratch(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    gpath = gdir / "genome_v1.json"
    (gpath).write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)

    run_web_quick(tmp_path, "classy", count=1, site="photoport")
    pid = "web_photoport_palette_01"
    original = load_palette_file(palette_dir, pid)["colors"][0]["hex"]
    roster_add(gdir, palette_dir, pid)

    result = tweak_palette(
        palette_dir,
        gpath,
        pid,
        action="reroll",
        genome_dir=gdir,
    )
    assert result["_studio_meta"]["bred_new"] is True
    assert result["id"] == "web_photoport_palette_02"
    kept = load_palette_file(palette_dir, pid)
    assert kept["colors"][0]["hex"] == original
