"""IDE palette schema and naming — no generate.py imports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

THEME_PREFIX = "RR"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_style(style_id: str) -> str:
    if style_id == "lemon_custard":
        return "lemon_cream"
    return style_id


def archetype_label(style_id: str) -> str:
    return normalize_style(style_id).replace("_", " ").title()


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
    """Picker label with RR prefix (theme_display_name / theme_name)."""
    for key in ("theme_display_name", "theme_name"):
        raw = str(palette.get(key) or "").strip()
        if raw:
            return with_theme_prefix(strip_theme_prefix(raw))
    meta = palette_meta(palette)
    return with_theme_prefix(archetype_label(meta["style_archetype"]))


def resolve_display_core(palette: dict[str, Any]) -> str:
    """Deprecated alias — returns branded name with RR prefix."""
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
) -> dict[str, Any]:
    style = normalize_style(style_archetype)
    branded = (
        with_theme_prefix(strip_theme_prefix(theme_name))
        if theme_name
        else with_theme_prefix(strip_theme_prefix(theme_display_name))
        if theme_display_name
        else with_theme_prefix(archetype_label(style))
    )
    ps_meta = genome.get("prompt_session") or {}
    return {
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
        "design_paradigms_applied": genome.get("design_paradigms", []),
        "techniques_applied": genome.get("techniques", []),
        "genome_version": genome.get("version", "1.0.0"),
        "generated": _iso_now(),
        "colors": colors,
        "palette_rationale": palette_rationale,
        "conflicts_flagged": [],
        "feedback_score": None,
        "feedback_dimensions": {},
        "user_prompt": user_prompt,
        **({"derived_from": derived_from} if derived_from else {}),
        **({"iteration_index": iteration_index} if iteration_index is not None else {}),
        "generation_controls": {
            "chromatic_variety": float(ps_meta.get("chromatic_variety", 0.55)),
            "prompt_adherence": float(ps_meta.get("prompt_adherence", 0.55)),
            "taste_mood_weighted": taste_mood_weighted,
        },
    }


def enrich_legacy_palette(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    meta = palette_meta(enriched)
    enriched.setdefault("style_archetype", meta["style_archetype"])
    enriched.setdefault("taste_mood", meta["taste_mood"])
    enriched.setdefault("is_light", meta["is_light"])
    branded = resolve_branded_name(enriched)
    enriched["theme_name"] = branded
    enriched["theme_display_name"] = branded
    return enriched
