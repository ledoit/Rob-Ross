"""IDE palette schema and naming — display-aligned slugs only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.sku import LEGACY_SLUG_ALIASES, normalize_slug, slug_to_display

THEME_PREFIX = "RR"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_style(style_id: str) -> str:
    return normalize_slug(style_id)


def style_display_name(style_id: str) -> str:
    """Picker label core (no RR prefix). Slug always Title-Cases to display."""
    return slug_to_display(normalize_style(style_id))


def archetype_label(style_id: str) -> str:
    return style_display_name(style_id)


def parse_taste_context(taste_context: str) -> dict[str, Any]:
    parts = str(taste_context or "").split(":")
    mood = parts[0] if parts and parts[0] else "nocturne_labs"
    style = normalize_style(parts[1]) if len(parts) >= 2 and parts[1] else "core"
    is_light = len(parts) >= 3 and parts[2] == "light"
    return {"taste_mood": mood, "style_archetype": style, "is_light": is_light}


def strip_theme_prefix(name: str) -> str:
    core = name.strip()
    lower = core.lower()
    for prefix in ("rob ross ", "robross ", "rr "):
        if lower.startswith(prefix):
            return core[len(prefix) :].strip()
    return core


def with_theme_prefix(label: str) -> str:
    core = strip_theme_prefix(label)
    return f"{THEME_PREFIX} {core}" if core else THEME_PREFIX


def palette_meta(palette: dict[str, Any]) -> dict[str, Any]:
    if palette.get("style_archetype") is not None:
        style = normalize_style(str(palette["style_archetype"]))
        mood = str(palette.get("taste_mood") or "nocturne_labs")
        is_light = bool(palette.get("is_light"))
    else:
        parsed = parse_taste_context(str(palette.get("taste_context", "")))
        style = parsed["style_archetype"]
        mood = parsed["taste_mood"]
        is_light = parsed["is_light"]
    return {
        "style_archetype": style,
        "taste_mood": mood,
        "is_light": is_light,
        "theme_mode": "light" if is_light else "dark",
    }


def resolve_branded_name(palette: dict[str, Any]) -> str:
    for key in ("theme_display_name", "theme_name"):
        raw = str(palette.get(key) or "").strip()
        if raw:
            return with_theme_prefix(strip_theme_prefix(raw))
    meta = palette_meta(palette)
    return with_theme_prefix(style_display_name(meta["style_archetype"]))


def resolve_display_core(palette: dict[str, Any]) -> str:
    return resolve_branded_name(palette)


def resolve_theme_name(palette: dict[str, Any]) -> str:
    return resolve_branded_name(palette)


def build_taste_context(*, taste_mood: str, style_archetype: str, is_light: bool) -> str:
    mode = "light" if is_light else "dark"
    return f"{taste_mood}:{normalize_style(style_archetype)}:{mode}"


def build_ide_palette_payload(
    *,
    palette_id: str,
    colors: list[dict[str, Any]],
    hue_family: str,
    taste_mood: str,
    style_archetype: str,
    is_light: bool,
    genome: dict[str, Any],
    user_prompt: str | None,
    palette_rationale: str,
    theme_display_name: str | None = None,
    theme_name: str | None = None,
    taste_mood_weighted: bool = False,
    derived_from: str | None = None,
    iteration_index: int | None = None,
    neighbors: list[str] | None = None,
) -> dict[str, Any]:
    style = normalize_style(style_archetype)
    branded = (
        with_theme_prefix(strip_theme_prefix(theme_name))
        if theme_name
        else with_theme_prefix(strip_theme_prefix(theme_display_name))
        if theme_display_name
        else with_theme_prefix(style_display_name(style))
    )
    ps_meta = genome.get("prompt_session") or {}
    payload: dict[str, Any] = {
        "id": palette_id,
        "context": "ide",
        "hue_family": hue_family,
        "style_archetype": style,
        "taste_mood": taste_mood,
        "is_light": is_light,
        "theme_name": branded,
        "theme_display_name": branded,
        "taste_context": build_taste_context(
            taste_mood=taste_mood, style_archetype=style, is_light=is_light
        ),
        "genome_version": genome.get("version", "2.0.0"),
        "generated": _iso_now(),
        "colors": colors,
        "palette_rationale": palette_rationale,
        "user_prompt": user_prompt,
        "generation_controls": {
            "chromatic_variety": float(ps_meta.get("chromatic_variety", 0.55)),
            "prompt_adherence": float(ps_meta.get("prompt_adherence", 0.55)),
            "taste_mood_weighted": taste_mood_weighted,
            "compounding": ps_meta.get("compounding"),
        },
    }
    if derived_from:
        payload["derived_from"] = derived_from
    if iteration_index is not None:
        payload["iteration_index"] = iteration_index
    if neighbors:
        payload["seeded_from"] = neighbors
    return payload


def enrich_legacy_palette(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    # Migrate legacy slugs in-place for readers
    raw_style = str(enriched.get("style_archetype") or "")
    if raw_style in LEGACY_SLUG_ALIASES:
        enriched["style_archetype"] = LEGACY_SLUG_ALIASES[raw_style]
    meta = palette_meta(enriched)
    enriched.setdefault("style_archetype", meta["style_archetype"])
    enriched.setdefault("taste_mood", meta["taste_mood"])
    enriched.setdefault("is_light", meta["is_light"])
    branded = resolve_branded_name(enriched)
    enriched["theme_name"] = branded
    enriched["theme_display_name"] = branded
    return enriched
