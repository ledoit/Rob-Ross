"""Tests for shared quick session (CLI + Studio)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from core.quick_session import list_ide_palette_meta, run_quick
from core.user_loop import delete_ide_palette_outputs as real_delete_ide_outputs
from core.roster import load_roster


def test_list_ide_palette_meta_skips_bad_files(tmp_path: Path) -> None:
    d = tmp_path
    (d / "ide_palette_01.json").write_text('{"id": "ide_palette_01", "generation_controls": {}}', encoding="utf-8")
    (d / "ide_palette_02.json").write_text("not json", encoding="utf-8")
    rows = list_ide_palette_meta(d)
    assert len(rows) == 1
    assert rows[0]["id"] == "ide_palette_01"


def test_run_quick_shortlist_replace_updates_roster(tmp_path: Path) -> None:
    root = tmp_path
    gdir = root / "genome"
    gdir.mkdir(parents=True)
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    genome = {
        "taste_contexts": {"ide": ["calm", "bold", "soft", "sharp"]},
        "style_archetypes": {"ide": ["a", "b", "c", "d"]},
        "prompt_session": {},
    }
    (gdir / "genome_v1.json").write_text(json.dumps(genome), encoding="utf-8")
    for pid in ["ide_palette_01", "ide_palette_02"]:
        (palette_dir / f"{pid}.json").write_text(
            json.dumps(
                {
                    "id": pid,
                    "generation_controls": {"chromatic_variety": 0.5, "prompt_adherence": 0.5},
                    "taste_context": "m:x:d",
                    "colors": [],
                }
            ),
            encoding="utf-8",
        )

    fake = {"generated_count": 1, "task_plan": "t", "palettes": [{"id": "ide_palette_01"}]}
    with patch("core.quick_session.generate_palettes", return_value=fake):
        run_quick(
            root,
            "ocean teal",
            count=1,
            fresh=False,
            shortlist_palette_ids=["ide_palette_02"],
        )
    r = load_roster(gdir)
    assert r["shortlist_ids"] == ["ide_palette_02"]


def test_run_quick_fresh_deletes_after_bias_reads_breeder(tmp_path: Path) -> None:
    """apply_shortlist_bias must see breeder JSON; then --fresh removes it."""
    root = tmp_path
    gdir = root / "genome"
    gdir.mkdir(parents=True)
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    genome = {
        "taste_contexts": {"ide": ["calm", "bold", "soft", "sharp"]},
        "style_archetypes": {"ide": ["a", "b", "c", "d"]},
        "prompt_session": {},
    }
    (gdir / "genome_v1.json").write_text(json.dumps(genome), encoding="utf-8")
    breeder_path = palette_dir / "ide_palette_99.json"
    breeder_path.write_text(
        json.dumps(
            {
                "id": "ide_palette_99",
                "generation_controls": {"chromatic_variety": 0.4, "prompt_adherence": 0.9},
                "taste_context": "m:arch:d",
                "colors": [],
            }
        ),
        encoding="utf-8",
    )

    seen_before_delete: list[bool] = []

    def wrapped_delete(p: Path) -> int:
        seen_before_delete.append(breeder_path.is_file())
        return real_delete_ide_outputs(p)

    fake = {"generated_count": 1, "task_plan": "t", "palettes": [{"id": "ide_palette_01"}]}
    with (
        patch("core.quick_session.generate_palettes", return_value=fake),
        patch("core.quick_session.delete_ide_palette_outputs", side_effect=wrapped_delete),
    ):
        run_quick(
            root,
            "gray",
            count=1,
            fresh=True,
            shortlist_palette_ids=["ide_palette_99"],
        )

    assert seen_before_delete == [True], "breeder file should exist when fresh-delete runs"
    assert not breeder_path.exists()
