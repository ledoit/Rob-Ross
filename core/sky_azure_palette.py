"""Curated RR Sky Azure — light sky / baby blue / azure wash."""

from __future__ import annotations

from typing import Any

from core.math_engine import contrast_ratio, hex_to_hsl

SKY_AZURE_ROLE_HEX: dict[str, str] = {
    "background": "#F0F8FF",
    "surface": "#E3F4FF",
    "border": "#B8DCFF",
    "muted": "#5B9CC8",
    "foreground": "#0C3D5C",
    "accent_primary": "#38BDF8",
    "accent_secondary": "#0284C7",
    "syntax_1": "#0D9488",
    "syntax_2": "#6366F1",
    "syntax_3": "#CA8A04",
    "syntax_4": "#1D4ED8",
    "syntax_5": "#7C3AED",
    "syntax_6": "#DC2626",
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
            "curated_sky_azure",
            "light_sky_blue_layers",
            "alice_blue_base",
            "no_neutral_grey",
        ],
        "rationale": f"{role} from RR Sky Azure: airy sky wash, baby-blue layers, crisp azure accents.",
    }


def build_sky_azure_colors() -> list[dict[str, Any]]:
    bg = SKY_AZURE_ROLE_HEX["background"]
    fg = SKY_AZURE_ROLE_HEX["foreground"]
    return [_color_entry(role, SKY_AZURE_ROLE_HEX[role], bg, fg) for role in ROLE_ORDER]
