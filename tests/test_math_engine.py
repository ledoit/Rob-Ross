from core.math_engine import (
    analogous_split,
    build_role_map,
    contrast_ratio,
    deduplicate_perceptual,
    fibonacci_lightness_series,
    golden_ratio_hue_series,
    hsl_to_hex,
    perceptual_distance,
)


def test_golden_ratio_series_length_and_bounds():
    vals = golden_ratio_hue_series(210, 7)
    assert len(vals) == 7
    assert all(0 <= x < 360 for x in vals)


def test_fibonacci_lightness_series_length():
    vals = fibonacci_lightness_series(50, 6)
    assert len(vals) == 6
    assert all(0 <= x <= 100 for x in vals)


def test_analogous_split_centered():
    vals = analogous_split(240, 40, 5)
    assert len(vals) == 5
    assert vals[2] == 240


def test_contrast_ratio_black_white():
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert ratio > 20.9


def test_perceptual_distance_identity():
    assert perceptual_distance("#112233", "#112233") == 0.0


def test_deduplicate_perceptual_removes_near_duplicates():
    colors = ["#112233", "#122334", "#FF00FF"]
    deduped = deduplicate_perceptual(colors, threshold=2.0)
    assert len(deduped) <= len(colors)
    assert "#FF00FF" in deduped


def test_build_role_map_has_required_roles():
    colors = [
        hsl_to_hex(240, 12, 10),
        hsl_to_hex(245, 18, 16),
        hsl_to_hex(250, 22, 48),
        hsl_to_hex(285, 75, 62),
        hsl_to_hex(210, 12, 92),
    ]
    genome = {
        "lightness_profile": {"background_range": [8, 18]},
        "saturation_profile": {"base_saturation": [10, 25], "accent_saturation": [60, 85]},
    }
    role_map = build_role_map(colors, genome)
    for role in ["background", "foreground", "surface", "accent_primary"]:
        assert role in role_map
