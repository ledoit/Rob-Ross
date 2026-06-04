"""Web Studio backend helpers."""

from __future__ import annotations

import json
from pathlib import Path

from core.studio_web import list_web_palette_meta, set_role_hex, studio_boot_payload, tweak_palette
from core.web_session import run_web_quick


def test_studio_boot_payload(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    (tmp_path / "outputs" / "palettes").mkdir(parents=True)
    boot = studio_boot_payload(tmp_path)
    assert "sites" in boot
    assert "harmonies" in boot


def test_set_role_accent(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    run_web_quick(tmp_path, "gold accent", count=1, site="reno")
    meta = list_web_palette_meta(tmp_path / "outputs" / "palettes")[0]
    pal = set_role_hex(tmp_path / "outputs" / "palettes", meta["id"], "accent_primary", "#aabb00")
    roles = {c["role"]: c["hex"] for c in pal["colors"]}
    assert roles["accent_primary"] == "#aabb00"


def test_tweak_reroll_keeps_id(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    gpath = gdir / "genome_v1.json"
    (gpath).write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    run_web_quick(tmp_path, "blue calm", count=1, site="generic")
    pid = list_web_palette_meta(tmp_path / "outputs" / "palettes")[0]["id"]
    pal = tweak_palette(tmp_path / "outputs" / "palettes", gpath, pid, action="reroll")
    assert pal["id"] == pid
