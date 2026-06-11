"""Per-website profiles: brand-lock neutrals, default harmony, theme mode."""

from __future__ import annotations

from typing import Any

# Roles that stay fixed when brand_lock is on (hand-tuned marketing chrome).
RENO_BRAND_LOCK: dict[str, str] = {
    "background": "#060607",
    "surface": "#0a0b0d",
    "elevated": "#101216",
    "foreground": "#ffffff",
    "muted": "#cdcdcd",
    "border": "#2e2e2e",
}

SITE_PROFILES: dict[str, dict[str, Any]] = {
    "reno": {
        "label": "Reno Studios (editorial dark marketing)",
        "theme_mode": "dark",
        "harmony_default": "analogous",
        "brand_lock": True,
        "locked_roles": dict(RENO_BRAND_LOCK),
        "accent_roles": ("accent_primary", "accent_secondary"),
        "ui_min_contrast": 4.5,
        "token_min_contrast": 3.0,
        "neutral_ui_hue": 240,
        "export_prefix": "rr",
        "notes": "Keeps grey/white ladder; generated hues only replace accent slots.",
    },
    "jobjeeves": {
        "label": "JobJeeves (product / hiring UI)",
        "theme_mode": "light",
        "harmony_default": "split_complementary",
        "brand_lock": False,
        "locked_roles": {},
        "accent_roles": ("accent_primary", "accent_secondary"),
        "ui_min_contrast": 4.5,
        "token_min_contrast": 3.0,
        "export_prefix": "jj",
        "notes": "Light shell; trustworthy blues/teals from brief.",
    },
    "photoport": {
        "label": "PhotoPort (portfolio / image-forward)",
        "theme_mode": "dark",
        "harmony_default": "monochromatic",
        "brand_lock": False,
        "locked_roles": {},
        "accent_roles": ("accent_primary", "accent_secondary"),
        "ui_min_contrast": 4.5,
        "token_min_contrast": 3.0,
        "export_prefix": "pp",
        "notes": "Near-neutral chrome so photography stays hero; accents minimal.",
    },
    "paid": {
        "label": "Paid planner (local product UI)",
        "theme_mode": "dark",
        "harmony_default": "split_complementary",
        "brand_lock": False,
        "locked_roles": {},
        "accent_roles": ("accent_primary", "accent_secondary"),
        "ui_min_contrast": 4.5,
        "token_min_contrast": 3.0,
        "export_prefix": "paid",
        "notes": "Site tokens for Employment/Paid; IDE palettes sync via web sync paid.",
    },
    "generic": {
        "label": "Any marketing / product site",
        "theme_mode": "dark",
        "harmony_default": "analogous",
        "brand_lock": False,
        "locked_roles": {},
        "accent_roles": ("accent_primary", "accent_secondary"),
        "ui_min_contrast": 4.5,
        "token_min_contrast": 3.0,
        "export_prefix": "web",
        "notes": "Default profile for new sites; add a profile here or in genome/web_consumers.json.",
    },
}


def normalize_site_id(site: str | None) -> str:
    key = (site or "generic").strip().lower().replace("_", "-")
    return key if key in SITE_PROFILES else "generic"


def get_site_profile(site: str | None) -> dict[str, Any]:
    return dict(SITE_PROFILES[normalize_site_id(site)])
