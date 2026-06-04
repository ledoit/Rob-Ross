"""Harmony geometry tests."""

from core.harmony import HARMONY_MODES, harmony_hues, harmony_swatches


def test_harmony_hues_triadic_spacing() -> None:
    hues = harmony_hues(0, "triadic", 3)
    assert len(hues) == 3
    assert abs((hues[1] - hues[0]) % 360 - 120) < 1 or abs((hues[1] - hues[0]) % 360 - 240) < 1


def test_harmony_swatches_count() -> None:
    sw = harmony_swatches(52, "analogous", count=5, variant_index=0)
    assert len(sw) == 5
    assert all(s.startswith("#") and len(s) == 7 for s in sw)


def test_all_modes_defined() -> None:
    assert "complementary" in HARMONY_MODES
    assert "split_complementary" in HARMONY_MODES
