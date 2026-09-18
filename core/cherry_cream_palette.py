"""Curated RR Cherry Cream — light cherry-rose shortcake (saved keeper)."""

from __future__ import annotations

from typing import Any

from core.math_engine import contrast_ratio, hex_to_hsl

CHERRY_ROLE_HEX: dict[str, str] = {
    "background": "#FFF5F8",
    "surface": "#FFE8F0",
    "border": "#FFB3C8",
    "muted": "#FF85A8",
    "foreground": "#B01040",
    "accent_primary": "#E82050",
    "accent_secondary": "#FF2D6F",
    "syntax_1": "#DB2777",
    "syntax_2": "#F472B6",
    "syntax_3": "#DC2626",
    "syntax_4": "#A11345",
    "syntax_5": "#FF2D6F",
    "syntax_6": "#EF4444",
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
            "curated_cherry_cream",
            "light_cherry_rose_layers",
            "cream_frosting_base",
            "no_neutral_grey",
        ],
        "rationale": f"{role} from RR Cherry Cream: frosting white, blush layers, happy cherry accents.",
    }


def build_cherry_cream_colors() -> list[dict[str, Any]]:
    bg = CHERRY_ROLE_HEX["background"]
    fg = CHERRY_ROLE_HEX["foreground"]
    return [_color_entry(role, CHERRY_ROLE_HEX[role], bg, fg) for role in ROLE_ORDER]
