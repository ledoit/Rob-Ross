"""Map short natural-language color prompts into genome merge patches.

Designed for local, deterministic parsing (no LLM required). Extend with more
lexicon entries or optional Ollama JSON later.
"""

from __future__ import annotations

from typing import Any

from core.generate import ARCHETYPE_PROFILES, IDE_STYLE_ARCHETYPES

# Hue centers (degrees) for simple color words
ACCENT_HUES: dict[str, float] = {
    "yellow": 52.0,
    "gold": 48.0,
    "amber": 45.0,
    "canary": 54.0,
    "lemon": 58.0,
    "orange": 28.0,
    "coral": 16.0,
    "red": 355.0,
    "crimson": 348.0,
    "rose": 338.0,
    "pink": 330.0,
    "magenta": 315.0,
    "purple": 285.0,
    "violet": 270.0,
    "indigo": 245.0,
    "blue": 220.0,
    "azure": 210.0,
    "cyan": 190.0,
    "teal": 175.0,
    "green": 135.0,
    "lime": 95.0,
    "chartreuse": 85.0,
}

DARK_WORDS = frozenset(
    {"black", "dark", "obsidian", "charcoal", "jet", "nero", "midnight", "ink", "void", "noir"}
)
LIGHT_WORDS = frozenset({"white", "light", "snow", "paper", "day", "bright"})


def _tokens(text: str) -> list[str]:
    t = text.lower().replace("-", " ").replace(" and ", " ")
    return [x.strip(".,;:!?\"'") for x in t.split() if x.strip()]


def _detect_accents(text: str) -> list[tuple[str, float]]:
    """Return (word, hue) in order of appearance (whole tokens only — no 'red' in 'desired')."""
    tokens = _tokens(text)
    token_set = set(tokens)
    found = [(w, ACCENT_HUES[w]) for w in ACCENT_HUES if w in token_set]
    found.sort(key=lambda wh: next((i for i, tok in enumerate(tokens) if tok == wh[0]), 999))
    return found


def archetypes_dark_first(ide_list: list[str] | None) -> list[str]:
    base = list(ide_list) if ide_list else list(IDE_STYLE_ARCHETYPES)
    dark = [a for a in base if str(ARCHETYPE_PROFILES.get(a, {}).get("theme_mode")) == "dark"]
    rest = [a for a in base if a not in dark]
    if not dark:
        return base
    return dark + rest


def genome_patch_from_prompt(text: str) -> dict[str, Any]:
    """Build a shallow+deep patch dict suitable for merge_genomes (session use)."""
    raw = text.strip()
    tl = raw.lower()
    patch: dict[str, Any] = {}
    ps: dict[str, Any] = {"source_text": raw}
    tokens = set(_tokens(raw))

    accents = _detect_accents(raw)
    if accents:
        ps["accent_hue_center"] = accents[0][1]
        ps["accent_hue_spread"] = 12.0
        ps["accent_words"] = [a[0] for a in accents]
        if len(accents) > 1:
            ps["accent_secondary_hue"] = accents[1][1]
        # Tight chroma + strong brief lock when user names explicit accent colors
        ps["chromatic_variety"] = 0.22
        ps["prompt_adherence"] = 0.9

    has_dark = bool(tokens & DARK_WORDS)
    has_light = bool(tokens & LIGHT_WORDS)

    if has_dark and not has_light:
        patch["lightness_profile"] = {
            "background_range": [3, 12],
            "foreground_range": [84, 98],
        }
        patch["saturation_profile"] = {"base_saturation": [8, 22]}
        ps["prefer_dark_theme_archetypes"] = True
    elif has_light and not has_dark:
        patch["lightness_profile"] = {
            "background_range": [92, 98],
            "foreground_range": [12, 26],
        }
        ps["prefer_light_theme_archetypes"] = True
    elif has_dark and has_light:
        # High contrast / split — bias dark UI with bright accent (common for "black and white")
        patch["lightness_profile"] = {"background_range": [6, 14], "foreground_range": [88, 98]}
        ps["prefer_dark_theme_archetypes"] = True

    if not accents and not has_dark and not has_light:
        # Still record prompt for palette metadata; no strong color steering
        ps["accent_hue_spread"] = 18.0

    if "chromatic_variety" not in ps:
        if has_dark or has_light:
            ps["chromatic_variety"] = 0.42
            ps["prompt_adherence"] = 0.62
        else:
            ps["chromatic_variety"] = 0.58
            ps["prompt_adherence"] = 0.48

    patch["prompt_session"] = ps
    return patch


def apply_prompt_archetype_order(genome: dict[str, Any]) -> None:
    """Mutate genome style_archetypes.ide in-place for dark/light preference."""
    ps = genome.get("prompt_session") or {}
    ide = list(genome.get("style_archetypes", {}).get("ide", IDE_STYLE_ARCHETYPES))
    if ps.get("prefer_dark_theme_archetypes"):
        genome.setdefault("style_archetypes", {})["ide"] = archetypes_dark_first(ide)
    elif ps.get("prefer_light_theme_archetypes"):
        light_first = [a for a in ide if str(ARCHETYPE_PROFILES.get(a, {}).get("theme_mode")) == "light"]
        rest = [a for a in ide if a not in light_first]
        if light_first:
            genome.setdefault("style_archetypes", {})["ide"] = light_first + rest
