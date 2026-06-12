"""Curated RR Velvet Rose — red velvet cake, cream frosting, strawberry layers.

References:
- Velvet crumb #3B0F14  deep burgundy cake
- Strawberry layer #5C1823 / #7A2438
- Cream cheese frosting #FFF5EE / #FFF8F0
- Strawberry pink #E8A4B8 / #FFB3C6
"""

from __future__ import annotations

from typing import Any

from core.math_engine import contrast_ratio, hex_to_hsl

VELVET_CRUMB = "#3B0F14"
STRAWBERRY_LAYER = "#5C1823"
LAYER_EDGE = "#7A2438"
DUSTY_ROSE = "#C48894"
CREAM_FROSTING = "#FFF5EE"
BRIGHT_FROSTING = "#FFF8F0"
STRAWBERRY_PINK = "#E8A4B8"
LIGHT_PINK = "#F5D6E0"
STRAWBERRY_CREAM = "#FFD4DC"
BERRY_RED = "#FF4466"
STRAWBERRY_ACCENT = "#FF6B8A"

VELVET_ROLE_HEX: dict[str, str] = {
    "background": VELVET_CRUMB,
    "surface": STRAWBERRY_LAYER,
    "border": LAYER_EDGE,
    "muted": DUSTY_ROSE,
    "foreground": CREAM_FROSTING,
    "accent_primary": BRIGHT_FROSTING,
    "accent_secondary": STRAWBERRY_PINK,
    "syntax_1": LIGHT_PINK,
    "syntax_2": STRAWBERRY_CREAM,
    "syntax_3": BRIGHT_FROSTING,
    "syntax_4": STRAWBERRY_ACCENT,
    "syntax_5": STRAWBERRY_PINK,
    "syntax_6": BERRY_RED,
}

ROLE_ORDER = [
    "background",
    "surface",
    "border",
    "muted",
    "foreground",
    "accent_primary",
    "accent_secondary",
    "syntax_1",
    "syntax_2",
    "syntax_3",
    "syntax_4",
    "syntax_5",
    "syntax_6",
]


def _color_entry(role: str, hx: str, bg: str, fg: str) -> dict[str, Any]:
    return {
        "role": role,
        "hex": hx,
        "hsl": list(hex_to_hsl(hx)),
        "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
        "contrast_with_background": round(contrast_ratio(hx, bg), 2),
        "genome_principles_applied": [
            "curated_velvet_rose",
            "red_velvet_cake_layers",
            "cream_frosting_contrast",
        ],
        "rationale": (
            f"{role} from velvet-cake palette: burgundy crumb, strawberry layers, cream frosting."
        ),
    }


def build_red_velvet_rose_colors() -> list[dict[str, Any]]:
    bg = VELVET_ROLE_HEX["background"]
    fg = VELVET_ROLE_HEX["foreground"]
    return [_color_entry(role, VELVET_ROLE_HEX[role], bg, fg) for role in ROLE_ORDER]
