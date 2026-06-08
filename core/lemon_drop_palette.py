"""Curated lemon-family IDE palettes from W3C/CSS reference swatches.

References:
- LemonChiffon #FFFACD  hsl(54°, 100%, 90%)
- Cornsilk #FFF8DC  hsl(48°, 100%, 93%)
- LightGoldenrodYellow #FAFAD2  hsl(60°, 80%, 91%)
- Gold #FFD700  hsl(51°, 100%, 50%)
"""

from __future__ import annotations

from typing import Any

from core.math_engine import contrast_ratio, hex_to_hsl

LEMON_CHIFFON = "#FFFACD"
CORNSILK = "#FFF8DC"
LIGHT_GOLDENROD_YELLOW = "#FAFAD2"
GOLD = "#FFD700"

# Lemon Cream / Lemon Custard — same swatches; gold focus, dark-gold selection.
CREAM_ROLE_HEX: dict[str, str] = {
    "background": LEMON_CHIFFON,
    "surface": CORNSILK,
    "border": LIGHT_GOLDENROD_YELLOW,
    "muted": "#7A6A1E",
    "foreground": "#361F4F",
    "accent_primary": GOLD,
    "accent_secondary": "#8B6914",
    "syntax_1": "#00695C",
    "syntax_2": "#6A1B9A",
    "syntax_3": "#7B4FAD",
    "syntax_4": "#5E35B1",
    "syntax_5": "#8B6914",
    "syntax_6": "#B71C1C",
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


def _color_entry(role: str, hx: str, bg: str, fg: str, *, tag: str) -> dict[str, Any]:
    return {
        "role": role,
        "hex": hx,
        "hsl": list(hex_to_hsl(hx)),
        "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
        "contrast_with_background": round(contrast_ratio(hx, bg), 2),
        "genome_principles_applied": [
            f"curated_{tag}",
            "w3c_lemon_family_swatches",
            "split_complement_syntax",
        ],
        "rationale": f"{role} from W3C lemon/cream reference swatches with violet split-complement syntax.",
    }


def _build_from_roles(role_hex: dict[str, str], tag: str) -> list[dict[str, Any]]:
    bg = role_hex["background"]
    fg = role_hex["foreground"]
    return [_color_entry(role, role_hex[role], bg, fg, tag=tag) for role in ROLE_ORDER]


def build_lemon_cream_colors() -> list[dict[str, Any]]:
    return _build_from_roles(CREAM_ROLE_HEX, "lemon_cream")


def build_lemon_custard_colors() -> list[dict[str, Any]]:
    return build_lemon_cream_colors()
