"""Canon remove / validate / repair — agent control surface tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.agent_api import discard, remove, repair, validate
from core.canon import UseRemoveError, is_kept_palette, validate_canon
from core.knowledge import load_priors, read_ledger
from core.layout import registry_dir
from core.roster import load_roster, roster_add
from core.sku import get_sku, load_skus, upsert_sku


def _minimal_palette(
    pid: str,
    *,
    slug: str,
    is_light: bool,
    bg: str,
    surface: str,
    accent: str = "#6D28D9",
) -> dict:
    roles = {
        "background": bg,
        "surface": surface,
        "border": "#D2C2E8",
        "muted": "#8B72A8",
        "foreground": "#2A1F3D" if is_light else "#FAFAFA",
        "accent_primary": accent,
        "accent_secondary": "#A21CAF",
        "syntax_1": "#5B21B6",
        "syntax_2": "#C026D3",
        "syntax_3": "#BE185D",
        "syntax_4": "#DB2777",
        "syntax_5": "#7C3AED",
        "syntax_6": "#9333EA",
    }
    colors = [{"role": r, "hex": hx} for r, hx in roles.items()]
    return {
        "id": pid,
        "context": "ide",
        "style_archetype": slug,
        "theme_display_name": f"RR {slug.replace('_', ' ').title()}",
        "theme_name": f"RR {slug.replace('_', ' ').title()}",
        "is_light": is_light,
        "hue_family": "violet",
        "taste_mood": "default",
        "colors": colors,
        "user_prompt": "test",
    }


def _boot(root: Path) -> None:
    for d in ("knowledge", "genome", "registry", "outputs/palettes"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "ledger.jsonl").write_text("", encoding="utf-8")
    (root / "knowledge" / "priors.json").write_text(
        json.dumps({"version": 2, "canon_count": 0, "slugs": [], "neighbor_index": []}),
        encoding="utf-8",
    )
    (root / "knowledge" / "skus.json").write_text(
        json.dumps({"version": 1, "skus": {}}), encoding="utf-8"
    )
    (root / "genome" / "genome_v1.json").write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "saturation_profile": {"base_saturation": [8, 22], "accent_saturation": [70, 90]},
                "lightness_profile": {
                    "background_range": [88, 96],
                    "foreground_range": [12, 22],
                    "midtone_range": [38, 58],
                },
                "style_archetypes": {"ide": []},
                "contrast_philosophy": {
                    "min_contrast_ratio": 4.5,
                    "ui_min_contrast_ratio": 4.5,
                    "token_min_contrast_ratio": 3.2,
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "registry" / "theme_tiers.json").write_text(
        json.dumps({"free": [], "pro": ["bubblegum"], "marketing_names": {}}),
        encoding="utf-8",
    )


def test_remove_by_slug_retires_full_canon(tmp_path: Path) -> None:
    root = tmp_path
    _boot(root)
    palette_dir = root / "outputs" / "palettes"
    pal = _minimal_palette(
        "ide_palette_17",
        slug="bubblegum",
        is_light=False,
        bg="#7A2D52",
        surface="#943866",
    )
    (palette_dir / "ide_palette_17.json").write_text(json.dumps(pal), encoding="utf-8")
    reg = registry_dir(root)
    roster_add(reg, palette_dir, "ide_palette_17")
    upsert_sku(
        root,
        "bubblegum",
        display="Bubblegum",
        rr_name="RR Bubblegum",
        tier="pro",
        mode="curated",
        palette_id="ide_palette_17",
        is_light=False,
    )

    with patch("core.ide_theme.finalize_ide_themes", return_value={"installed": False}):
        result = remove(root, "bubblegum")

    assert result["removed"] is True
    assert result["slug"] == "bubblegum"
    assert "ide_palette_17" not in load_roster(reg)["palette_ids"]
    assert get_sku(root, "bubblegum") is None
    assert not (palette_dir / "ide_palette_17.json").is_file()
    tiers = json.loads((root / "registry" / "theme_tiers.json").read_text(encoding="utf-8"))
    assert "bubblegum" not in tiers.get("pro", [])
    ledger = read_ledger(root)
    assert ledger[-1]["type"] == "remove"
    assert ledger[-1]["slug"] == "bubblegum"
    priors = load_priors(root)
    assert "bubblegum" not in priors.get("slugs", [])
    assert validate(root) == []


def test_discard_rejects_kept_palette(tmp_path: Path) -> None:
    root = tmp_path
    _boot(root)
    palette_dir = root / "outputs" / "palettes"
    pal = _minimal_palette(
        "ide_palette_12",
        slug="lemon_haze",
        is_light=True,
        bg="#FFFACD",
        surface="#FFF5B0",
    )
    (palette_dir / "ide_palette_12.json").write_text(json.dumps(pal), encoding="utf-8")
    reg = registry_dir(root)
    roster_add(reg, palette_dir, "ide_palette_12")
    assert is_kept_palette(root, "ide_palette_12")

    with pytest.raises(UseRemoveError):
        discard(root, "ide_palette_12")


def test_discard_allows_unkept_draft(tmp_path: Path) -> None:
    root = tmp_path
    _boot(root)
    palette_dir = root / "outputs" / "palettes"
    pal = _minimal_palette(
        "ide_palette_99",
        slug="draft_theme",
        is_light=False,
        bg="#111111",
        surface="#222222",
    )
    (palette_dir / "ide_palette_99.json").write_text(json.dumps(pal), encoding="utf-8")

    with patch("core.ide_theme.finalize_ide_themes", return_value={"installed": False}):
        result = discard(root, "ide_palette_99")

    assert result["discarded"] is True
    assert not (palette_dir / "ide_palette_99.json").is_file()
    ledger = read_ledger(root)
    assert ledger[-1]["type"] == "discard"


def test_validate_detects_orphan_sku(tmp_path: Path) -> None:
    root = tmp_path
    _boot(root)
    upsert_sku(
        root,
        "ghost",
        display="Ghost",
        tier="pro",
        palette_id="ide_palette_99",
        is_light=False,
    )
    issues = validate_canon(root)
    assert any("orphan SKU ghost" in i for i in issues)


def test_repair_clears_orphan_sku(tmp_path: Path) -> None:
    root = tmp_path
    _boot(root)
    upsert_sku(
        root,
        "ghost",
        display="Ghost",
        tier="pro",
        palette_id="ide_palette_99",
        is_light=False,
    )
    with patch("core.ide_theme.finalize_ide_themes", return_value={"installed": False}):
        result = repair(root)
    assert "ghost" not in load_skus(root).get("skus", {})
    assert result["issues_after"] == []
