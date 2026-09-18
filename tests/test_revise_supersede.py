"""Revise / supersede flow — iterate kept themes; keep replaces DNA."""

from __future__ import annotations

import json
from pathlib import Path

from core.ide_iteration import (
    _resolve_superseded_palette_id,
    infer_style_from_prompt,
    keep_ide_palette,
    load_palette,
)
from core.ide_theme import make_ide_palette
from core.knowledge import load_priors, role_map
from core.layout import registry_dir
from core.revise import nudge_roles_from_feedback
from core.roster import load_roster, roster_add
from core.sku import get_sku, upsert_sku


def _minimal_palette(
    pid: str,
    *,
    slug: str,
    is_light: bool,
    bg: str,
    surface: str,
    accent: str = "#6D28D9",
    derived_from: str | None = None,
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
        "derived_from": derived_from,
        "user_prompt": "test",
    }


def test_infer_violet_mist() -> None:
    assert infer_style_from_prompt("violet mist more haze") == "violet_mist"


def test_nudge_more_haze_raises_chrome_sat() -> None:
    roles = {
        "background": "#F5F0FB",
        "surface": "#EBE3F5",
        "border": "#D2C2E8",
        "muted": "#8B72A8",
        "foreground": "#2A1F3D",
        "accent_primary": "#6D28D9",
        "accent_secondary": "#A21CAF",
    }
    from core.math_engine import hex_to_hsl

    before = hex_to_hsl(roles["background"])[1]
    out = nudge_roles_from_feedback(
        roles, "more purple haziness overall", is_light=True, variety=0.7
    )
    after = hex_to_hsl(out["background"])[1]
    assert after > before
    assert out["background"] != roles["background"]


def test_nudge_lime_locks_accent_toward_95() -> None:
    roles = {
        "background": "#F7F8F7",
        "surface": "#E7E9E8",
        "border": "#DBE1DC",
        "muted": "#87A18F",
        "foreground": "#272124",
        "accent_primary": "#099A10",
        "accent_secondary": "#3B9716",
        "syntax_1": "#3B9E1A",
    }
    from core.math_engine import hex_to_hsl

    before = hex_to_hsl(roles["accent_primary"])[0]
    out = nudge_roles_from_feedback(roles, "more lime on accents", is_light=True)
    after = hex_to_hsl(out["accent_primary"])[0]
    def circ(a: float, b: float) -> float:
        return min(abs(a - b), 360 - abs(a - b))
    assert circ(after, 95.0) < circ(before, 95.0)


def test_iterate_kept_sku_changes_hexes(tmp_path: Path) -> None:
    """Iterate must not freeze-reload canon for a kept SKU."""
    root = tmp_path
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (root / "knowledge").mkdir(parents=True)
    (root / "genome").mkdir(parents=True)
    (root / "registry").mkdir(parents=True)
    (root / "knowledge" / "priors.json").write_text(
        json.dumps(
            {
                "version": 2,
                "canon_count": 1,
                "keep_count": 1,
                "discard_count": 0,
                "dark": {},
                "light": {
                    "count": 1,
                    "accent_hue_center": 263,
                    "accent_hues": [263],
                    "bg_light_mean": 96,
                    "bg_light_range": [94, 97],
                    "bg_sat_mean": 50,
                    "accent_sat_mean": 70,
                    "syntax_spread_mean": 100,
                    "slugs": ["violet_mist"],
                },
                "occupied_accents": [{"slug": "violet_mist", "hue": 263, "is_light": True}],
                "slugs": ["violet_mist"],
                "neighbor_index": [
                    {
                        "slug": "violet_mist",
                        "palette_id": "ide_palette_22",
                        "accent_hue": 263,
                        "is_light": True,
                        "roles": {
                            "background": "#F5F0FB",
                            "accent_primary": "#6D28D9",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "knowledge" / "skus.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skus": {
                    "violet_mist": {
                        "display": "Violet Mist",
                        "rr_name": "RR Violet Mist",
                        "tier": "pro",
                        "mode": "curated",
                        "palette_id": "ide_palette_22",
                        "is_light": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "knowledge" / "ledger.jsonl").write_text("", encoding="utf-8")
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
                "style_archetypes": {"ide": ["violet_mist"]},
                "contrast_philosophy": {
                    "min_contrast_ratio": 4.5,
                    "ui_min_contrast_ratio": 4.5,
                    "token_min_contrast_ratio": 3.2,
                },
            }
        ),
        encoding="utf-8",
    )
    parent = _minimal_palette(
        "ide_palette_22",
        slug="violet_mist",
        is_light=True,
        bg="#F5F0FB",
        surface="#EBE3F5",
    )
    (palette_dir / "ide_palette_22.json").write_text(json.dumps(parent), encoding="utf-8")
    reg = registry_dir(root)
    roster_add(reg, palette_dir, "ide_palette_22")
    upsert_sku(
        root,
        "violet_mist",
        display="Violet Mist",
        rr_name="RR Violet Mist",
        tier="pro",
        mode="curated",
        palette_id="ide_palette_22",
        is_light=True,
    )

    result = make_ide_palette(
        root,
        "more purple haziness in the paper",
        style="violet_mist",
        is_light=True,
        derived_from="ide_palette_22",
        iteration_index=1,
        export=False,
        install=False,
        package_vsix=False,
    )
    child_id = result["palette_id"]
    assert child_id != "ide_palette_22"
    child = load_palette(root, child_id)
    assert child["style_archetype"] == "violet_mist"
    assert role_map(child)["background"] != role_map(parent)["background"]
    # DNA unchanged until keep
    assert "ide_palette_22" in load_roster(reg)["palette_ids"]
    assert child_id not in load_roster(reg)["palette_ids"]


def test_keep_replaces_old_in_roster_and_sku(tmp_path: Path) -> None:
    root = tmp_path
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (root / "knowledge").mkdir(parents=True)
    (root / "genome").mkdir(parents=True)
    (root / "registry").mkdir(parents=True)
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
                "style_archetypes": {"ide": ["violet_mist"]},
                "contrast_philosophy": {
                    "min_contrast_ratio": 4.5,
                    "ui_min_contrast_ratio": 4.5,
                    "token_min_contrast_ratio": 3.2,
                },
            }
        ),
        encoding="utf-8",
    )

    old = _minimal_palette(
        "ide_palette_22", slug="violet_mist", is_light=True, bg="#F5F0FB", surface="#EBE3F5"
    )
    new = _minimal_palette(
        "ide_palette_23",
        slug="violet_mist",
        is_light=True,
        bg="#EFE4FA",
        surface="#E0D2F2",
        derived_from="ide_palette_22",
    )
    (palette_dir / "ide_palette_22.json").write_text(json.dumps(old), encoding="utf-8")
    (palette_dir / "ide_palette_23.json").write_text(json.dumps(new), encoding="utf-8")
    reg = registry_dir(root)
    roster_add(reg, palette_dir, "ide_palette_22")
    upsert_sku(
        root,
        "violet_mist",
        display="Violet Mist",
        rr_name="RR Violet Mist",
        tier="pro",
        mode="curated",
        palette_id="ide_palette_22",
        is_light=True,
    )

    assert _resolve_superseded_palette_id(root, new, "violet_mist") == "ide_palette_22"

    from unittest.mock import patch

    with patch("core.ide_theme.finalize_ide_themes", return_value={"installed": False}):
        result = keep_ide_palette(root, "ide_palette_23")

    assert result["kept"] is True
    assert result["replaced"] == "ide_palette_22"
    roster_ids = load_roster(reg)["palette_ids"]
    assert "ide_palette_23" in roster_ids
    assert "ide_palette_22" not in roster_ids
    sku = get_sku(root, "violet_mist")
    assert sku is not None
    assert sku["palette_id"] == "ide_palette_23"
    assert sku["tier"] == "pro"
    priors = load_priors(root)
    assert priors["canon_count"] == 1
    assert "violet_mist" in priors["slugs"]
    # DNA uses successor hexes
    mist_row = next(r for r in priors["neighbor_index"] if r["slug"] == "violet_mist")
    assert mist_row["palette_id"] == "ide_palette_23"
    assert mist_row["roles"]["background"] == "#EFE4FA"


def test_detect_fork_intent() -> None:
    from core.revise import detect_fork_intent, wants_rich_purple_shades

    assert detect_fork_intent("keep violet mist but iterate a new one alongside")
    assert detect_fork_intent("second palette with more purple")
    assert not detect_fork_intent("more haze on the paper")
    assert wants_rich_purple_shades("way more shades of purple twilight lake light theme")


def test_fork_iterate_new_slug_keeps_parent_on_keep(tmp_path: Path) -> None:
    from unittest.mock import patch

    from core.ide_iteration import iterate_ide_palette, keep_ide_palette

    root = tmp_path
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True)
    (root / "knowledge").mkdir(parents=True)
    (root / "genome").mkdir(parents=True)
    (root / "registry").mkdir(parents=True)
    (root / "knowledge" / "ledger.jsonl").write_text("", encoding="utf-8")
    (root / "knowledge" / "priors.json").write_text(
        json.dumps(
            {
                "version": 2,
                "canon_count": 1,
                "slugs": ["violet_mist"],
                "neighbor_index": [
                    {
                        "slug": "violet_mist",
                        "palette_id": "ide_palette_22",
                        "is_light": True,
                        "accent_hue": 263,
                        "roles": {"background": "#F5F0FB"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "knowledge" / "skus.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skus": {
                    "violet_mist": {
                        "palette_id": "ide_palette_22",
                        "tier": "pro",
                        "mode": "curated",
                        "is_light": True,
                    }
                },
            }
        ),
        encoding="utf-8",
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
                "style_archetypes": {"ide": ["violet_mist"]},
                "contrast_philosophy": {
                    "min_contrast_ratio": 4.5,
                    "ui_min_contrast_ratio": 4.5,
                    "token_min_contrast_ratio": 3.2,
                },
            }
        ),
        encoding="utf-8",
    )
    parent = _minimal_palette(
        "ide_palette_22", slug="violet_mist", is_light=True, bg="#F5F0FB", surface="#EBE3F5"
    )
    (palette_dir / "ide_palette_22.json").write_text(json.dumps(parent), encoding="utf-8")
    reg = registry_dir(root)
    roster_add(reg, palette_dir, "ide_palette_22")

    with patch("core.ide_theme.finalize_ide_themes", return_value={"installed": False}):
        draft = iterate_ide_palette(
            root,
            "keep violet mist but iterate a new light theme with way more shades of purple twilight lake",
            from_palette_id="ide_palette_22",
            fork=True,
        )
        child_id = draft["palette_id"]
        child = load_palette(root, child_id)
        assert child["style_archetype"] != "violet_mist"
        assert child["derived_from"] == "ide_palette_22"
        assert role_map(child)["background"] != role_map(parent)["background"]

        kept = keep_ide_palette(root, child_id)

    assert kept["replaced"] is None
    roster_ids = load_roster(reg)["palette_ids"]
    assert "ide_palette_22" in roster_ids
    assert child_id in roster_ids
    priors = load_priors(root)
    assert priors["canon_count"] == 2
    assert "violet_mist" in priors["slugs"]
    assert child["style_archetype"] in priors["slugs"]
