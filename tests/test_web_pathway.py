"""Website pathway — contrast, brand-lock, CSS export."""

from __future__ import annotations

import json
from pathlib import Path

from core.export.css_site_tokens import palette_to_css
from core.pathways.web import build_web_palette
from core.pathways.web_sites import RENO_BRAND_LOCK
from core.web_session import run_web_quick


def test_reno_brand_lock_keeps_background() -> None:
    genome = {"version": "1.1.0", "prompt_session": {"accent_hue_center": 52}}
    pal = build_web_palette(genome, site="reno", harmony_mode="triadic")
    roles = {c["role"]: c["hex"] for c in pal["colors"]}
    assert roles["background"].lower() == RENO_BRAND_LOCK["background"].lower()
    assert roles["foreground"].lower() == RENO_BRAND_LOCK["foreground"].lower()
    assert "accent_primary" in roles


def test_foreground_contrast_sane() -> None:
    genome = {"version": "1.1.0", "prompt_session": {"accent_hue_center": 210}}
    pal = build_web_palette(genome, site="jobjeeves", harmony_mode="analogous")
    fg = next(c for c in pal["colors"] if c["role"] == "foreground")
    assert fg["contrast_with_background"] >= 3.0


def test_css_export_reno() -> None:
    genome = {"version": "1.1.0", "prompt_session": {"accent_hue_center": 45}}
    pal = build_web_palette(genome, site="reno")
    css = palette_to_css(pal, site="reno")
    assert "--site-accent-primary" in css
    assert "--palette-dark-900" in css


def test_run_web_quick_writes_files(tmp_path: Path) -> None:
    gdir = tmp_path / "genome"
    gdir.mkdir()
    (gdir / "genome_v1.json").write_text(
        json.dumps({"version": "1.1.0", "prompt_session": {}}),
        encoding="utf-8",
    )
    result = run_web_quick(tmp_path, "gold accent editorial", count=2, site="photoport")
    assert result["generated_count"] == 2
    assert (tmp_path / "outputs" / "palettes" / "web_photoport_palette_01.json").is_file()
