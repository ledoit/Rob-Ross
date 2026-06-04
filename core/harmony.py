"""Color-harmony geometry (Coolors-style) — deterministic hue arrangements.

Coolors does not publish its exact RNG; publicly it behaves like classic color-theory
rules (analogous, complementary, triadic, …) plus randomized saturation/lightness while
respecting locked swatches. This module implements that pattern in HSL.
"""

from __future__ import annotations

import random
from typing import Any

from core.math_engine import hex_to_hsl, hsl_to_hex

HARMONY_MODES = (
    "monochromatic",
    "analogous",
    "complementary",
    "split_complementary",
    "triadic",
    "tetradic",
    "square",
)


def _norm_h(h: float) -> float:
    return h % 360.0


def harmony_hues(base_hue: float, mode: str, count: int = 5) -> list[float]:
    """Return `count` hues arranged by harmony mode (Coolors-style geometry)."""
    if count <= 0:
        return []
    h = _norm_h(base_hue)
    mode = mode if mode in HARMONY_MODES else "analogous"

    if mode == "monochromatic":
        return [h] * count

    if mode == "analogous":
        if count == 1:
            return [h]
        spread = 50.0
        step = spread / (count - 1)
        left = h - spread / 2
        return [_norm_h(left + i * step) for i in range(count)]

    if mode == "complementary":
        comp = _norm_h(h + 180)
        anchors = [h, comp]
        return [anchors[i % 2] for i in range(count)]

    if mode == "split_complementary":
        anchors = [h, _norm_h(h + 150), _norm_h(h + 210)]
        return [anchors[i % 3] for i in range(count)]

    if mode == "triadic":
        anchors = [h, _norm_h(h + 120), _norm_h(h + 240)]
        return [anchors[i % 3] for i in range(count)]

    if mode == "tetradic":
        anchors = [h, _norm_h(h + 60), _norm_h(h + 180), _norm_h(h + 240)]
        return [anchors[i % 4] for i in range(count)]

    # square — four corners of the hue wheel (+ repeat)
    anchors = [h, _norm_h(h + 90), _norm_h(h + 180), _norm_h(h + 270)]
    return [anchors[i % 4] for i in range(count)]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def harmony_swatches(
    base_hue: float,
    mode: str,
    *,
    count: int = 5,
    variant_index: int = 0,
    theme_mode: str = "dark",
    sat_base: tuple[float, float] = (12.0, 28.0),
    sat_accent: tuple[float, float] = (55.0, 82.0),
    light_bg: float = 12.0,
    light_fg: float = 96.0,
    light_mid: float = 48.0,
    seed: int | None = None,
) -> list[str]:
    """
    Build `count` hex swatches: harmony hues + Fibonacci-ish lightness ladder + sat bands.

    `variant_index` nudges hues/sat/light so spacebar-style rerolls differ deterministically.
    """
    hues = harmony_hues(base_hue, mode, count)
    is_light = theme_mode == "light"
    rng = random.Random(seed if seed is not None else variant_index * 7919 + int(base_hue))

    # Coolors-like: chrome slots muted, last slots more saturated
    hexes: list[str] = []
    for i, hue in enumerate(hues):
        t = i / max(1, count - 1)
        jitter_h = (rng.random() - 0.5) * (6.0 + variant_index * 0.4)
        hue = _norm_h(hue + jitter_h)

        if i >= count - 2:
            sat = _clamp(sat_accent[0] + t * (sat_accent[1] - sat_accent[0]) + rng.uniform(-4, 6), 35, 95)
        else:
            sat = _clamp(sat_base[0] + t * (sat_base[1] - sat_base[0]) + rng.uniform(-3, 4), 4, 45)

        if is_light:
            light = _clamp(light_bg - i * 2.5 + rng.uniform(-2, 2), 88, 98) if i == 0 else _clamp(
                light_mid + (i - 1) * 4 + rng.uniform(-3, 3), 22, 72
            )
            if i == count - 1:
                light = _clamp(light_fg - 82, 12, 28)
        else:
            if i == 0:
                light = _clamp(light_bg + rng.uniform(-2, 2), 6, 20)
            elif i == count - 1:
                light = _clamp(light_fg + rng.uniform(-2, 2), 88, 98)
            else:
                light = _clamp(light_mid + (i - 1) * 3.5 + rng.uniform(-4, 4), 28, 62)

        hexes.append(hsl_to_hex(hue, sat, light))
    return hexes


def shuffle_swatches(
    swatches: list[str],
    *,
    frozen_indices: set[int] | None = None,
    base_hue: float,
    mode: str,
    variant_index: int,
) -> list[str]:
    """Regenerate unlocked positions (Coolors lock + spacebar)."""
    frozen = frozen_indices or set()
    out = list(swatches)
    need = [i for i in range(len(out)) if i not in frozen]
    if not need:
        return out
    fresh = harmony_swatches(base_hue, mode, count=len(need), variant_index=variant_index + 1)
    for idx, hx in zip(need, fresh):
        out[idx] = hx
    return out


def describe_harmony(mode: str) -> str:
    """One-line explanation for docs / CLI."""
    notes: dict[str, str] = {
        "monochromatic": "Same hue; lightness and saturation carry the palette.",
        "analogous": "Neighboring hues (~50° fan) — calm, cohesive UI chrome.",
        "complementary": "Base hue + opposite (180°) — high punch, use sparingly on accents.",
        "split_complementary": "Base + two neighbors of the complement — balanced pop.",
        "triadic": "Three hues 120° apart — vibrant, game/marketing friendly.",
        "tetradic": "Two complementary pairs (60° steps) — rich, needs restraint.",
        "square": "Four hues 90° apart — bold editorial / poster energy.",
    }
    return notes.get(mode, notes["analogous"])
