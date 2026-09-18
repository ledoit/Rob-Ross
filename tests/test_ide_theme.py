"""IDE theme pipeline tests."""

from __future__ import annotations

from core.ide_schema import (
    archetype_label,
    build_ide_palette_payload,
    build_taste_context,
    enrich_legacy_palette,
    parse_taste_context,
    resolve_theme_name,
    strip_theme_prefix,
    style_display_name,
    with_theme_prefix,
)


def test_theme_name_from_archetype() -> None:
    payload = build_ide_palette_payload(
        palette_id="ide_palette_11",
        colors=[{"role": "background", "hex": "#111111"}],
        hue_family="amber",
        taste_mood="nocturne_labs",
        style_archetype="high_contrast_signal",
        is_light=False,
        genome={"prompt_session": {}, "design_paradigms": [], "techniques": [], "version": "1.0.0"},
        user_prompt="high contrast",
        palette_rationale="test rationale",
    )
    assert payload["theme_name"] == "RR High Contrast Signal"
    assert payload["style_archetype"] == "high_contrast_signal"


def test_style_display_name_word_counts() -> None:
    assert style_display_name("cherry_cream") == "Cherry Cream"
    assert style_display_name("high_contrast_signal") == "High Contrast Signal"


def test_theme_name_custom_display() -> None:
    payload = build_ide_palette_payload(
        palette_id="ide_palette_14",
        colors=[{"role": "background", "hex": "#FFFACD"}],
        hue_family="amber",
        taste_mood="studio_neon",
        style_archetype="lemon_cream",
        is_light=True,
        genome={"prompt_session": {}, "design_paradigms": [], "techniques": [], "version": "1.0.0"},
        user_prompt="lemon cream",
        palette_rationale="test rationale",
        theme_display_name="Lemon Custard",
    )
    assert payload["theme_name"] == "RR Lemon Custard"
    assert payload["is_light"] is True


def test_parse_taste_context() -> None:
    parsed = parse_taste_context("nocturne_labs:lemon_paper:light")
    assert parsed == {"taste_mood": "nocturne_labs", "style_archetype": "lemon_haze", "is_light": True}


def test_enrich_legacy_palette() -> None:
    legacy = {"taste_context": "fjord_ink:fjord_hammer:light", "theme_display_name": "Fjord Hammer"}
    enriched = enrich_legacy_palette(legacy)
    assert enriched["is_light"] is True
    assert enriched["style_archetype"] == "fjord_hammer"
    assert enriched["theme_display_name"] == "RR Fjord Hammer"


def test_prefix_helpers() -> None:
    assert strip_theme_prefix("Rob Ross Lemon Haze") == "Lemon Haze"
    assert with_theme_prefix("Lemon Haze") == "RR Lemon Haze"
    assert with_theme_prefix("Bubblegum") == "RR Bubblegum"


def test_curated_theme_names() -> None:
    assert archetype_label("cherry_cream") == "Cherry Cream"
    cherry = build_ide_palette_payload(
        palette_id="ide_palette_15",
        colors=[{"role": "background", "hex": "#FFF5F8"}],
        hue_family="red",
        taste_mood="studio_neon",
        style_archetype="cherry_cream",
        is_light=True,
        genome={"prompt_session": {}, "design_paradigms": [], "techniques": [], "version": "1.0.0"},
        user_prompt="cherry cream",
        palette_rationale="test",
    )
    assert cherry["theme_name"] == "RR Cherry Cream"


def test_build_taste_context() -> None:
    assert build_taste_context(taste_mood="studio_neon", style_archetype="lemon_custard", is_light=True) == (
        "studio_neon:lemon_custard:light"
    )
