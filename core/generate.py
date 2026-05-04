"""Genome-guided palette generation and superset construction."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from core.math_engine import (
    analogous_split,
    build_role_map,
    contrast_ratio,
    deduplicate_perceptual,
    fibonacci_lightness_series,
    golden_ratio_hue_series,
    hex_to_hsl,
    hsl_to_hex,
    perceptual_distance,
)

console = Console()

IDE_HUE_FAMILIES: list[tuple[str, int]] = [
    ("cyan", 190),
    ("azure", 210),
    ("blue", 225),
    ("indigo", 245),
    ("violet", 265),
    ("purple", 285),
    ("magenta", 315),
    ("red", 355),
    ("orange", 28),
    ("amber", 45),
    ("green", 135),
]

IDE_STYLE_ARCHETYPES: list[str] = [
    "dracula_punch",
    "fjord_hammer",
    "alpenglow_paper",
    "kimbie_warm",
    "ion_storm",
    "forest_canopy",
    "void_forge",
    "bonfire_gold",
    "candy_voltage",
    "night_siren",
    "high_contrast_signal",
]

HARD_KEEP_ARCHETYPES = {
    "dracula_punch",
    "kimbie_warm",
    "ion_storm",
    "candy_voltage",
    "high_contrast_signal",
}

TASTE_CONTEXT_PROFILES: dict[str, dict[str, float]] = {
    "nocturne_labs": {"sat_bias": -4.0, "accent_sat_bias": 2.0, "syntax_light_bias": 3.0, "hue_offset": 0.0},
    "fjord_ink": {"sat_bias": -2.0, "accent_sat_bias": 1.0, "syntax_light_bias": 2.0, "hue_offset": 8.0},
    "retro_terminal": {"sat_bias": 3.0, "accent_sat_bias": 6.0, "syntax_light_bias": 1.0, "hue_offset": -10.0},
    "studio_neon": {"sat_bias": 5.0, "accent_sat_bias": 10.0, "syntax_light_bias": 5.0, "hue_offset": 14.0},
    "forest_console": {"sat_bias": -1.0, "accent_sat_bias": 4.0, "syntax_light_bias": 2.0, "hue_offset": -6.0},
}

ARCHETYPE_PROFILES: dict[str, dict[str, Any]] = {
    "dracula_punch": {"relation_mode": "triadic", "ui_sat_bias": 8, "accent_boost": 18, "syntax_light_base": 70, "bg_light": 9, "surface_delta": 7, "fg_hue_shift": 26, "theme_mode": "dark"},
    "fjord_hammer": {"relation_mode": "analogous", "ui_sat_bias": -5, "accent_boost": 2, "syntax_light_base": 50, "bg_light": 98, "surface_delta": 6, "fg_hue_shift": 205, "theme_mode": "light"},
    "alpenglow_paper": {"relation_mode": "analogous", "ui_sat_bias": -9, "accent_boost": -2, "syntax_light_base": 48, "bg_light": 96, "surface_delta": 5, "fg_hue_shift": 24, "theme_mode": "light"},
    "kimbie_warm": {"relation_mode": "warm_split", "ui_sat_bias": -2, "accent_boost": 2, "syntax_light_base": 57, "bg_light": 14, "surface_delta": 5, "fg_hue_shift": 30, "theme_mode": "dark"},
    "ion_storm": {"relation_mode": "neon_depth", "ui_sat_bias": 14, "accent_boost": 28, "syntax_light_base": 78, "bg_light": 6, "surface_delta": 2, "fg_hue_shift": 34, "theme_mode": "dark"},
    "forest_canopy": {"relation_mode": "analogous", "ui_sat_bias": -6, "accent_boost": 3, "syntax_light_base": 58, "bg_light": 11, "surface_delta": 4, "fg_hue_shift": 18, "theme_mode": "dark"},
    "void_forge": {"relation_mode": "triadic", "ui_sat_bias": 4, "accent_boost": 10, "syntax_light_base": 62, "bg_light": 4, "surface_delta": 3, "fg_hue_shift": 42, "theme_mode": "dark"},
    "bonfire_gold": {
        "relation_mode": "warm_split",
        "ui_sat_bias": 12,
        "accent_boost": 30,
        "syntax_light_base": 62,
        "bg_light": 90,
        "surface_delta": 8,
        "fg_hue_shift": 12,
        "fg_light": 16,
        "fg_sat_boost": 22,
        "theme_mode": "light",
    },
    "candy_voltage": {"relation_mode": "triadic", "ui_sat_bias": 10, "accent_boost": 21, "syntax_light_base": 72, "bg_light": 8, "surface_delta": 6, "fg_hue_shift": 24, "theme_mode": "dark"},
    "night_siren": {"relation_mode": "split", "ui_sat_bias": 10, "accent_boost": 22, "syntax_light_base": 74, "bg_light": 6, "surface_delta": 3, "fg_hue_shift": 350, "theme_mode": "dark"},
    "high_contrast_signal": {"relation_mode": "split", "ui_sat_bias": 10, "accent_boost": 24, "syntax_light_base": 74, "bg_light": 6, "surface_delta": 8, "fg_hue_shift": 28, "theme_mode": "dark"},
}

SEMANTIC_HUE_ANCHORS: dict[str, float] = {
    "nocturne": 255,
    "night": 235,
    "deep": 225,
    "blue": 220,
    "cool": 210,
    "ocean": 200,
    "abyss": 248,
    "neon": 300,
    "dracula": 290,
    "warm": 28,
    "earth": 34,
    "kimbie": 30,
    "amber": 45,
    "signal": 120,
    "high_contrast": 110,
    "editorial": 52,
    "mono": 210,
    "split": 350,
    "triadic": 315,
    "solarized": 193,
    "forest": 135,
    "retro": 18,
    "studio": 320,
    "fjord": 205,
    "magenta": 315,
    "purple": 285,
    "green": 130,
}

ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "dracula_punch": ["dracula", "nocturne", "magenta", "purple"],
    "fjord_hammer": ["fjord", "ice", "sky", "baby blue", "light", "cyan"],
    "alpenglow_paper": ["paper", "light", "warm", "calm", "editorial"],
    "kimbie_warm": ["warm", "earth", "kimbie", "amber"],
    "ion_storm": ["abyss", "deep", "neon", "signal", "studio"],
    "forest_canopy": ["forest", "green", "earth", "calm"],
    "void_forge": ["void", "forge", "charcoal", "crimson", "violet", "dark"],
    "bonfire_gold": ["bonfire", "fire", "gold", "orange", "amber", "warm", "sunset"],
    "candy_voltage": ["triadic", "neon", "magenta", "studio"],
    "night_siren": ["red", "night", "siren", "signal", "dark"],
    "high_contrast_signal": ["high_contrast", "signal", "green"],
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_generation_task(task: str) -> dict[str, int]:
    lowered = task.lower()
    ide_count = 0
    web_count = 0
    superset_count = 0

    for count, context in re.findall(r"(\d+)\s+(ide|web)\s+palettes?", lowered):
        if context == "ide":
            ide_count += int(count)
        else:
            web_count += int(count)

    superset_match = re.search(r"superset\s+of\s+(\d+)", lowered)
    if superset_match:
        superset_count = int(superset_match.group(1))

    return {"ide": ide_count, "web": web_count, "superset": superset_count}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ensure_min_contrast(color_hex: str, bg_hex: str, min_ratio: float) -> str:
    if contrast_ratio(color_hex, bg_hex) >= min_ratio:
        return color_hex

    hue, sat, light = hex_to_hsl(color_hex)
    bg_light = hex_to_hsl(bg_hex)[2]
    move_lighter = bg_light <= 50
    for step in range(1, 30):
        delta = step * 2
        candidate_light = _clamp(light + delta, 5, 95) if move_lighter else _clamp(light - delta, 5, 95)
        candidate_sat = _clamp(sat - step * 0.4, 20, 95)
        candidate = hsl_to_hex(hue, candidate_sat, candidate_light)
        if contrast_ratio(candidate, bg_hex) >= min_ratio:
            return candidate
    return color_hex


def _select_taste_context(genome: dict[str, Any], context: str, variant_index: int) -> str:
    configured = genome.get("taste_contexts", {}).get(context, [])
    if not configured:
        return "default"
    return str(configured[variant_index % len(configured)])


def _build_support_hues(base_hue: float, count: int, relation_mode: str) -> list[float]:
    if count <= 0:
        return []
    if relation_mode == "analogous":
        return analogous_split((base_hue + 180) % 360, 80, count)
    if relation_mode == "split":
        return analogous_split((base_hue + 180) % 360, 130, count)
    if relation_mode == "triadic":
        anchors = [base_hue % 360, (base_hue + 120) % 360, (base_hue + 240) % 360]
        return [anchors[i % 3] for i in range(count)]
    if relation_mode == "monochrome":
        return [base_hue for _ in range(count)]
    if relation_mode == "solarized":
        canonical = [45, 18, 8, 331, 267, 205, 175, 95]
        return [canonical[i % len(canonical)] for i in range(count)]
    if relation_mode == "warm_split":
        anchors = [28, 42, 55, (base_hue + 205) % 360, (base_hue + 232) % 360]
        return [anchors[i % len(anchors)] for i in range(count)]
    if relation_mode == "neon_depth":
        anchors = [(base_hue + 175) % 360, (base_hue + 210) % 360, 52, 198]
        return [anchors[i % len(anchors)] for i in range(count)]
    return golden_ratio_hue_series((base_hue + 180) % 360, count)


def _circular_mean(degrees: list[float]) -> float:
    if not degrees:
        return 220.0
    x = sum(math.cos(math.radians(d)) for d in degrees)
    y = sum(math.sin(math.radians(d)) for d in degrees)
    angle = math.degrees(math.atan2(y, x))
    return angle % 360


def _derive_archetype_hue(genome: dict[str, Any], archetype_name: str, taste_context: str) -> float:
    terms: list[str] = []
    terms.extend(ARCHETYPE_KEYWORDS.get(archetype_name, []))
    terms.extend(str(x).replace("_", " ") for x in genome.get("design_paradigms", []))
    terms.extend(str(x).replace("_", " ") for x in genome.get("techniques", []))
    terms.extend([taste_context.replace("_", " "), archetype_name.replace("_", " ")])

    hue_votes: list[float] = []
    for term in terms:
        lowered = term.lower()
        for key, hue in SEMANTIC_HUE_ANCHORS.items():
            if key in lowered:
                hue_votes.append(hue)

    base = _circular_mean(hue_votes)
    jitter = (sum(ord(c) for c in f"{taste_context}:{archetype_name}") % 21) - 10
    return (base + jitter) % 360


def _nearest_family(hue: float) -> str:
    family, _ = min(IDE_HUE_FAMILIES, key=lambda item: min(abs(hue - item[1]), 360 - abs(hue - item[1])))
    return family


def _enforce_token_distance(hexes: list[str], min_distance: float) -> list[str]:
    adjusted: list[str] = []
    for idx, hx in enumerate(hexes):
        candidate = hx
        h, s, l = hex_to_hsl(candidate)
        attempts = 0
        while attempts < 24 and any(perceptual_distance(candidate, prev) < min_distance for prev in adjusted):
            shift = 11 + (idx % 3) * 7
            candidate = hsl_to_hex((h + shift * (attempts + 1)) % 360, min(95, s + 2), l)
            attempts += 1
        adjusted.append(candidate)
    return adjusted


def _llm_palette_rationale(genome: dict[str, Any], context: str, role_map: dict[str, str]) -> str:
    if os.getenv("ROBROSS_USE_LLM_RATIONALE", "0").strip().lower() not in {"1", "true", "yes"}:
        return f"Generated with deterministic {context} profile derived from genome settings."

    try:
        from llama_index.llms.ollama import Ollama
    except Exception:
        return f"Generated with deterministic {context} profile derived from genome settings."

    model_name = os.getenv("ROBROSS_OLLAMA_MODEL", "mistral")
    prompt = f"""
Write a concise design rationale for this generated {context} palette.
Reference genome principles explicitly and keep it technical.

Genome excerpt:
{json.dumps(genome, indent=2)[:3000]}

Role map:
{json.dumps(role_map, indent=2)}
"""
    try:
        llm = Ollama(model=model_name, request_timeout=120.0)
        return llm.complete(prompt).text.strip()
    except Exception:
        return f"Generated with deterministic {context} profile derived from genome settings."


def _build_palette_colors(
    genome: dict[str, Any], context: str, palette_size: int = 9, variant_index: int = 0
) -> tuple[list[dict[str, Any]], str, str]:
    hue_cfg = genome.get("hue_strategy", {})
    sat_cfg = genome.get("saturation_profile", {})
    light_cfg = genome.get("lightness_profile", {})

    base_range = hue_cfg.get("base_hue_range", [210, 270])
    default_base_hue = (base_range[0] + base_range[1]) / 2
    family_name = "core"
    contrast_cfg = genome.get("contrast_philosophy", {})
    ui_min_contrast = float(contrast_cfg.get("ui_min_contrast_ratio", contrast_cfg.get("min_contrast_ratio", 4.5)))
    token_min_contrast = float(contrast_cfg.get("token_min_contrast_ratio", 3.2))

    if context == "ide":
        ide_cfg = genome.get("context_overrides", {}).get("ide", {})
        tone = ide_cfg.get("tone_controls", {})
        taste_context = _select_taste_context(genome, context, variant_index)
        taste_profile = TASTE_CONTEXT_PROFILES.get(taste_context, {})
        paradigms = set(genome.get("design_paradigms", []))
        techniques = set(genome.get("techniques", []))
        archetypes = genome.get("style_archetypes", {}).get("ide", IDE_STYLE_ARCHETYPES)
        archetype_name = str(archetypes[variant_index % len(archetypes)]) if archetypes else IDE_STYLE_ARCHETYPES[variant_index % len(IDE_STYLE_ARCHETYPES)]
        archetype = ARCHETYPE_PROFILES.get(archetype_name, ARCHETYPE_PROFILES["fjord_hammer"])
        base_hue = _derive_archetype_hue(genome, archetype_name, taste_context)
        family_name = _nearest_family(base_hue)
        base_hue = (base_hue + taste_profile.get("hue_offset", 0.0)) % 360
        accent_primary_h = base_hue
        accent_secondary_h = (base_hue + 28) % 360
        syntax_count = max(3, int(ide_cfg.get("syntax_color_count", 6)))
        support_hues = _build_support_hues(base_hue, syntax_count, str(archetype.get("relation_mode", "analogous")))

        base_sat = sat_cfg.get("base_saturation", [10, 25])
        acc_sat = sat_cfg.get("accent_saturation", [60, 85])
        bg_range = light_cfg.get("background_range", [8, 18])
        fg_range = light_cfg.get("foreground_range", [85, 97])
        mid_range = light_cfg.get("midtone_range", [40, 60])
        calmness = float(_clamp(float(tone.get("calmness", 0.7)), 0.0, 1.0))
        vibrancy = float(_clamp(float(tone.get("vibrancy", 0.6)), 0.0, 1.0))
        separation = float(_clamp(float(tone.get("separation", 0.7)), 0.0, 1.0))

        if "split_complementary_syntax_distribution" in techniques and str(archetype.get("relation_mode")) == "analogous":
            support_hues = analogous_split((base_hue + 180) % 360, 120, len(support_hues))
        if "semantic_separation" in paradigms:
            separation = _clamp(separation + 0.15, 0.0, 1.0)
        if "low_fatigue_long_sessions" in paradigms:
            calmness = _clamp(calmness + 0.1, 0.0, 1.0)
            vibrancy = _clamp(vibrancy - 0.1, 0.0, 1.0)

        accent_sat_floor = (
            max(acc_sat[0], 45 + 20 * vibrancy)
            + taste_profile.get("accent_sat_bias", 0.0)
            + float(archetype.get("accent_boost", 0.0))
        )
        accent_sat_peak = max(accent_sat_floor + 5, acc_sat[1] - (1 - vibrancy) * 8)
        muted_light = _clamp(mid_range[0] - (calmness * 4), 30, 55)
        syntax_base_light = _clamp(
            float(archetype.get("syntax_light_base", 53)) + separation * 8 + taste_profile.get("syntax_light_bias", 0.0), 48, 75
        )
        base_sat_low = _clamp(base_sat[0] + taste_profile.get("sat_bias", 0.0) + float(archetype.get("ui_sat_bias", 0.0)), 4, 45)
        base_sat_high = _clamp(base_sat[1] + taste_profile.get("sat_bias", 0.0) + float(archetype.get("ui_sat_bias", 0.0)), 8, 55)

        theme_mode = str(archetype.get("theme_mode", "dark"))
        is_light = theme_mode == "light"
        bg_light_default = bg_range[0] + 1 if not is_light else 94
        bg_light = _clamp(float(archetype.get("bg_light", bg_light_default)), 5, 97)
        surface_delta = _clamp(float(archetype.get("surface_delta", 5)), 3, 9)
        fg_hue_shift = float(archetype.get("fg_hue_shift", 12))
        if is_light:
            fg_light = float(archetype.get("fg_light", 14))
            fg_sat_boost = float(archetype.get("fg_sat_boost", 0))
            role_map = {
                "background": hsl_to_hex(base_hue, max(2, base_sat_low - 8), bg_light),
                "surface": hsl_to_hex((base_hue + 8) % 360, max(3, base_sat_low - 5), bg_light - surface_delta),
                "border": hsl_to_hex((base_hue + 10) % 360, max(6, base_sat_high - 8), bg_light - surface_delta - 4),
                "muted": hsl_to_hex((base_hue + 16) % 360, max(8, base_sat_high - 5), min(58, bg_light - 36)),
                "foreground": hsl_to_hex((base_hue + fg_hue_shift) % 360, max(8, base_sat_low + 2 + fg_sat_boost), fg_light),
                "accent_primary": hsl_to_hex(accent_primary_h, accent_sat_peak, 46),
                "accent_secondary": hsl_to_hex(accent_secondary_h, accent_sat_floor, 42),
            }
        else:
            role_map = {
                "background": hsl_to_hex(base_hue, max(4, base_sat_low - 2), bg_light),
                "surface": hsl_to_hex((base_hue + 8) % 360, max(6, base_sat_low + 2), bg_light + surface_delta),
                "border": hsl_to_hex((base_hue + 10) % 360, base_sat_high, bg_light + surface_delta + 2),
                "muted": hsl_to_hex((base_hue + 16) % 360, base_sat_high, muted_light),
                "foreground": hsl_to_hex((base_hue + fg_hue_shift) % 360, max(4, base_sat_low - 4), fg_range[1]),
                "accent_primary": hsl_to_hex(accent_primary_h, accent_sat_peak, 62),
                "accent_secondary": hsl_to_hex(accent_secondary_h, accent_sat_floor, 58),
            }

        syntax_hexes: list[str] = []
        for idx, hue in enumerate(support_hues):
            syntax_sat = accent_sat_floor - (idx % 4) * 4
            syntax_hexes.append(hsl_to_hex(hue, syntax_sat, syntax_base_light - (idx % 3) * 4))
        syntax_hexes = _enforce_token_distance(syntax_hexes, float(ide_cfg.get("min_token_distance", 14.0)))
        for idx, hx in enumerate(syntax_hexes):
            role_map[f"syntax_{idx + 1}"] = hx

        bg = role_map["background"]
        if "simultaneous_contrast_balancing" in techniques:
            token_min_contrast = max(token_min_contrast, 3.6)
            ui_min_contrast = max(ui_min_contrast, 4.8)

        role_contrast_targets = (
            {
                "surface": 1.08,
                "border": 1.2,
                "muted": 2.5,
                "foreground": ui_min_contrast,
                "accent_primary": 3.2,
                "accent_secondary": 3.2,
            }
            if is_light
            else {
                "surface": 1.15,
                "border": 1.45,
                "muted": 2.8,
                "foreground": ui_min_contrast,
                "accent_primary": 3.1,
                "accent_secondary": 3.1,
            }
        )
        for role in ("surface", "border", "muted", "foreground", "accent_primary", "accent_secondary"):
            role_map[role] = _ensure_min_contrast(role_map[role], bg, role_contrast_targets[role])

        for role in [r for r in role_map if r.startswith("syntax_")]:
            role_map[role] = _ensure_min_contrast(role_map[role], bg, token_min_contrast)

        fg = role_map["foreground"]
        colors = []
        for role, hx in role_map.items():
            colors.append(
                {
                    "role": role,
                    "hex": hx,
                    "hsl": list(hex_to_hsl(hx)),
                    "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
                    "contrast_with_background": round(contrast_ratio(hx, role_map["background"]), 2),
                    "genome_principles_applied": [
                        "genome_driven_math_engine",
                        f"context_{context}",
                        f"hue_family_{family_name}",
                    ],
                    "rationale": f"{role} tuned for {family_name} family while preserving dark-editor readability.",
                }
            )
        return colors, family_name, f"{taste_context}:{archetype_name}:{theme_mode}"

    base_hue = default_base_hue + (variant_index * 11)
    hue_series = golden_ratio_hue_series(base_hue, palette_size)
    if context == "web":
        accent_range = hue_cfg.get("accent_hue_range", [280, 320])
        hue_series = analogous_split((accent_range[0] + accent_range[1]) / 2, 60, palette_size)

    light_series = fibonacci_lightness_series((light_cfg.get("midtone_range", [40, 60])[0] + light_cfg.get("midtone_range", [40, 60])[1]) / 2, palette_size)
    base_sat = sat_cfg.get("base_saturation", [10, 25])
    acc_sat = sat_cfg.get("accent_saturation", [60, 85])

    hexes = []
    for idx in range(palette_size):
        sat = base_sat[0] + (idx / max(1, palette_size - 1)) * (base_sat[1] - base_sat[0])
        if idx >= palette_size - 2:
            sat = acc_sat[0] + ((idx - (palette_size - 2)) / 2) * (acc_sat[1] - acc_sat[0])
        hexes.append(hsl_to_hex(hue_series[idx], sat, light_series[idx]))

    deduped = deduplicate_perceptual(hexes, threshold=5.0)
    role_map = build_role_map(deduped, genome)
    fg = role_map.get("foreground", deduped[-1])

    colors = []
    for role, hx in role_map.items():
        hsl = list(hex_to_hsl(hx))
        colors.append(
            {
                "role": role,
                "hex": hx,
                "hsl": hsl,
                "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
                "contrast_with_background": round(contrast_ratio(hx, role_map.get("background", hx)), 2),
                "genome_principles_applied": ["genome_driven_math_engine", f"context_{context}"],
                "rationale": f"{role} selected via deterministic role assignment from lightness/saturation bands.",
            }
        )
    return colors, family_name, _select_taste_context(genome, context, variant_index)


def generate_palettes(task: str, genome: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    plan = parse_generation_task(task)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated: list[dict[str, Any]] = []
    for context in ("ide", "web"):
        for i in range(plan[context]):
            palette_id = f"{context}_palette_{i + 1:02d}"
            palette_path = out / f"{palette_id}.json"
            if context == "ide":
                archetypes = genome.get("style_archetypes", {}).get("ide", IDE_STYLE_ARCHETYPES)
                archetype_name = str(archetypes[i % len(archetypes)]) if archetypes else IDE_STYLE_ARCHETYPES[i % len(IDE_STYLE_ARCHETYPES)]
                if archetype_name in HARD_KEEP_ARCHETYPES and palette_path.exists():
                    existing = json.loads(palette_path.read_text(encoding="utf-8"))
                    generated.append(existing)
                    continue
            colors, family_name, taste_context = _build_palette_colors(genome, context=context, variant_index=i)
            role_map = {c["role"]: c["hex"] for c in colors}
            payload = {
                "id": palette_id,
                "context": context,
                "hue_family": family_name,
                "taste_context": taste_context,
                "design_paradigms_applied": genome.get("design_paradigms", []),
                "techniques_applied": genome.get("techniques", []),
                "genome_version": genome.get("version", "1.0.0"),
                "generated": _iso_now(),
                "colors": colors,
                "palette_rationale": _llm_palette_rationale(genome, context, role_map),
                "conflicts_flagged": [],
                "feedback_score": None,
                "feedback_dimensions": {},
            }
            with palette_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            generated.append(payload)

    return {"task_plan": plan, "generated_count": len(generated), "palettes": generated}


def build_superset_from_palettes(input_palettes_dir: str | Path, count: int = 25) -> dict[str, Any]:
    palette_dir = Path(input_palettes_dir)
    files = sorted(palette_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No palette JSON files found in: {palette_dir}")

    all_colors: list[str] = []
    for p in files:
        data = json.loads(p.read_text(encoding="utf-8"))
        for c in data.get("colors", []):
            all_colors.append(c.get("hex"))

    deduped = deduplicate_perceptual([c for c in all_colors if c], threshold=8.0)
    selected = deduped[:count]
    coverage = {
        "total_input_colors": len(all_colors),
        "deduplicated_colors": len(deduped),
        "selected_count": len(selected),
        "selection_ratio": round((len(selected) / max(1, len(all_colors))) * 100, 2),
    }
    return {"generated": _iso_now(), "colors": selected, "coverage_analysis": coverage}
