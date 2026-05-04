"""Deterministic color math utilities for RobRoss Palette OS.

This module intentionally contains no LLM dependencies.
"""

from __future__ import annotations

import colorsys
import math
from typing import Any

import numpy as np
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor

if not hasattr(np, "asscalar"):
    np.asscalar = lambda arr: arr.item()  # type: ignore[attr-defined]


PHI = (1 + math.sqrt(5)) / 2


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_hue(hue: float) -> float:
    return hue % 360.0


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Expected 6-char hex color, got: {hex_color!r}")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return r, g, b


def _rgb01_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(round(_clamp(r, 0.0, 1.0) * 255)),
        int(round(_clamp(g, 0.0, 1.0) * 255)),
        int(round(_clamp(b, 0.0, 1.0) * 255)),
    )


def hex_to_hsl(hex_color: str) -> tuple[int, int, int]:
    r, g, b = _hex_to_rgb01(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return int(round(h * 360)) % 360, int(round(s * 100)), int(round(l * 100))


def hsl_to_hex(h: float, s: float, l: float) -> str:
    rgb = colorsys.hls_to_rgb((h % 360) / 360.0, _clamp(l / 100.0, 0.0, 1.0), _clamp(s / 100.0, 0.0, 1.0))
    return _rgb01_to_hex(*rgb)


def golden_ratio_hue_series(base_hue: float, n: int) -> list[float]:
    if n <= 0:
        return []
    step = 360 / PHI
    return [_normalize_hue(base_hue + i * step) for i in range(n)]


def fibonacci_lightness_series(base_l: float, n: int) -> list[float]:
    if n <= 0:
        return []
    base_l = _clamp(base_l, 0, 100)
    if n == 1:
        return [base_l]

    fib = [1, 1]
    while len(fib) < n + 1:
        fib.append(fib[-1] + fib[-2])
    max_f = fib[n]
    normalized = [f / max_f for f in fib[1 : n + 1]]
    spread = 30.0
    return [_clamp(base_l + (x - 0.5) * spread, 0, 100) for x in normalized]


def analogous_split(base_hue: float, spread_degrees: float, n: int) -> list[float]:
    if n <= 0:
        return []
    if n == 1:
        return [_normalize_hue(base_hue)]
    left = base_hue - spread_degrees / 2
    step = spread_degrees / (n - 1)
    return [_normalize_hue(left + i * step) for i in range(n)]


def perceptual_distance(color_a_hex: str, color_b_hex: str) -> float:
    a_r, a_g, a_b = _hex_to_rgb01(color_a_hex)
    b_r, b_g, b_b = _hex_to_rgb01(color_b_hex)
    lab_a: LabColor = convert_color(sRGBColor(a_r, a_g, a_b), LabColor)
    lab_b: LabColor = convert_color(sRGBColor(b_r, b_g, b_b), LabColor)
    return float(delta_e_cie2000(lab_a, lab_b))


def _relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb01(hex_color)

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lr, lg, lb = linearize(r), linearize(g), linearize(b)
    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def deduplicate_perceptual(hex_list: list[str], threshold: float = 8.0) -> list[str]:
    if threshold <= 0:
        return list(dict.fromkeys(c.upper() if c.startswith("#") else f"#{c.upper()}" for c in hex_list))

    kept: list[str] = []
    for color in hex_list:
        normalized = color.upper()
        if not normalized.startswith("#"):
            normalized = f"#{normalized}"
        if not kept:
            kept.append(normalized)
            continue
        if all(perceptual_distance(normalized, existing) >= threshold for existing in kept):
            kept.append(normalized)
    return kept


def build_role_map(hex_list: list[str], genome: dict[str, Any]) -> dict[str, str]:
    if not hex_list:
        return {}

    sorted_colors = sorted(hex_list, key=lambda h: hex_to_hsl(h)[2])
    lightness_cfg = genome.get("lightness_profile", {})
    sat_cfg = genome.get("saturation_profile", {})

    roles: dict[str, str] = {}
    roles["background"] = sorted_colors[0]
    roles["foreground"] = sorted_colors[-1]
    if len(sorted_colors) > 1:
        roles["surface"] = sorted_colors[min(1, len(sorted_colors) - 1)]
        roles["muted"] = sorted_colors[len(sorted_colors) // 2]

    base_sat_max = sat_cfg.get("base_saturation", [10, 25])[1]
    accent_sat_min = sat_cfg.get("accent_saturation", [60, 85])[0]
    bg_max = lightness_cfg.get("background_range", [8, 18])[1]

    accents = []
    border = None
    for color in sorted_colors:
        _h, s, l = hex_to_hsl(color)
        if border is None and l <= bg_max + 15 and s <= base_sat_max + 10:
            border = color
        if s >= accent_sat_min:
            accents.append(color)

    if border:
        roles["border"] = border
    if accents:
        roles["accent_primary"] = accents[0]
        if len(accents) > 1:
            roles["accent_secondary"] = accents[1]
    else:
        roles["accent_primary"] = sorted_colors[-2] if len(sorted_colors) > 1 else sorted_colors[0]

    return roles
