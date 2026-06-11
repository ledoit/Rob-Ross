"""Iteration loop tests."""

from __future__ import annotations

import json
from pathlib import Path

from core.ide_iteration import (
    _tweak_controls_from_feedback,
    infer_style_from_prompt,
    kept_palette_ids,
    load_iteration_session,
    record_draft,
    ship_palette_ids,
)
from core.layout import registry_dir
from core.roster import roster_add, roster_remove


def test_infer_style_lemon_cream() -> None:
    assert infer_style_from_prompt("lemon custard light") == "lemon_cream"
    assert infer_style_from_prompt("lemon yellow haze") == "lemon_paper"


def test_infer_style_ion() -> None:
    assert infer_style_from_prompt("dark ocean teal abyss") == "ion_storm"


def test_tweak_controls_brighter() -> None:
    v, a = _tweak_controls_from_feedback("make it brighter and punchier", 0.5, 0.7)
    assert v > 0.5
    assert a == 0.7


def test_kept_palette_ids_empty_by_default(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    assert kept_palette_ids(reg) == []


def test_ship_palette_ids_kept_plus_draft(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    for pid in ("ide_palette_01", "ide_palette_99"):
        (palette_dir / f"{pid}.json").write_text(
            json.dumps({"id": pid, "context": "ide", "colors": []}),
            encoding="utf-8",
        )
    roster_add(reg, palette_dir, "ide_palette_01")
    record_draft(tmp_path, "ide_palette_99", "test draft", derived_from=None)
    ids = ship_palette_ids(tmp_path)
    assert ids == ["ide_palette_01", "ide_palette_99"]


def test_ship_palette_ids_draft_not_duplicated_when_kept(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (palette_dir / "ide_palette_12.json").write_text(
        json.dumps({"id": "ide_palette_12", "context": "ide", "colors": []}),
        encoding="utf-8",
    )
    roster_add(reg, palette_dir, "ide_palette_12")
    record_draft(tmp_path, "ide_palette_12", "lemon", derived_from=None)
    assert ship_palette_ids(tmp_path) == ["ide_palette_12"]


def test_discard_removes_from_kept(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    palette_dir = tmp_path / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (palette_dir / "ide_palette_08.json").write_text(
        json.dumps({"id": "ide_palette_08", "context": "ide", "colors": []}),
        encoding="utf-8",
    )
    roster_add(reg, palette_dir, "ide_palette_08")
    roster_remove(reg, "ide_palette_08")
    assert kept_palette_ids(reg) == []


def test_session_chain(tmp_path: Path) -> None:
    reg = registry_dir(tmp_path)
    record_draft(tmp_path, "ide_palette_12", "lemon", derived_from=None)
    record_draft(tmp_path, "ide_palette_14", "lemon cream", derived_from="ide_palette_12")
    session = load_iteration_session(reg)
    assert session["draft_palette_id"] == "ide_palette_14"
    assert "ide_palette_12" in session["chain"]
    assert "ide_palette_14" in session["chain"]
