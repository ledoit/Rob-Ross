"""Website palette pathway — Coolors-style harmonies + WCAG roles + site brand-lock."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.harmony import HARMONY_MODES, harmony_swatches
from core.math_engine import contrast_ratio, hex_to_hsl, hsl_to_hex
from core.pathways.web_sites import get_site_profile, normalize_site_id
from core.prompt_brief import genome_patch_from_prompt


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


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


def _nearest_family(hue: float) -> str:
    families = [
        (0, "red"),
        (28, "orange"),
        (45, "amber"),
        (135, "green"),
        (190, "cyan"),
        (225, "blue"),
        (265, "violet"),
        (315, "magenta"),
    ]
    best = families[0][1]
    best_d = 999.0
    for anchor, name in families:
        d = min(abs(hue - anchor), 360 - abs(hue - anchor))
        if d < best_d:
            best_d = d
            best = name
    return best


def _swatches_to_role_map(
    swatches: list[str],
    profile: dict[str, Any],
    *,
    genome: dict[str, Any],
) -> dict[str, str]:
    """Map harmony swatches → semantic web roles with contrast repair."""
    theme_mode = str(profile.get("theme_mode", "dark"))
    is_light = theme_mode == "light"
    locked = dict(profile.get("locked_roles") or {})
    brand_lock = bool(profile.get("brand_lock")) and locked

    sat_cfg = genome.get("saturation_profile", {})
    light_cfg = genome.get("lightness_profile", {})
    sat_base = tuple(sat_cfg.get("base_saturation", [10, 25]))
    sat_acc = tuple(sat_cfg.get("accent_saturation", [60, 85]))
    bg_light = float(light_cfg.get("background_range", [8, 18])[0 if not is_light else 1])
    fg_light = float(light_cfg.get("foreground_range", [85, 97])[1 if not is_light else 0])
    mid_light = sum(light_cfg.get("midtone_range", [40, 60])) / 2

    sorted_sw = sorted(swatches, key=lambda h: hex_to_hsl(h)[2])
    if brand_lock:
        role_map = {
            k: v
            for k, v in locked.items()
            if k in ("background", "surface", "elevated", "foreground", "muted", "border")
        }
        accents = sorted(swatches, key=lambda h: hex_to_hsl(h)[1], reverse=True)[:2]
        if len(accents) >= 1:
            role_map["accent_primary"] = accents[0]
        if len(accents) >= 2:
            role_map["accent_secondary"] = accents[1]
        if "background" not in role_map:
            role_map["background"] = sorted_sw[0]
        if "foreground" not in role_map:
            role_map["foreground"] = sorted_sw[-1]
    else:
        role_map = {
            "background": sorted_sw[0],
            "surface": sorted_sw[min(1, len(sorted_sw) - 1)],
            "muted": sorted_sw[len(sorted_sw) // 2],
            "foreground": sorted_sw[-1],
            "border": sorted_sw[min(2, len(sorted_sw) - 1)],
        }
        accents = sorted(swatches, key=lambda h: hex_to_hsl(h)[1], reverse=True)
        role_map["accent_primary"] = accents[0]
        role_map["accent_secondary"] = accents[1] if len(accents) > 1 else accents[0]

    ui_min = float(profile.get("ui_min_contrast", 4.5))
    token_min = float(profile.get("token_min_contrast", 3.0))
    bg = role_map.get("background", sorted_sw[0])

    targets = {
        "surface": 1.12 if is_light else 1.15,
        "border": 1.25 if is_light else 1.4,
        "muted": 2.5,
        "foreground": ui_min,
        "accent_primary": token_min,
        "accent_secondary": token_min,
    }
    for role, target in targets.items():
        if role in role_map and not (brand_lock and role in locked):
            hx = role_map[role]
            if hx.startswith("#"):
                role_map[role] = _ensure_min_contrast(hx, bg, target)

    return role_map


def build_web_palette(
    genome: dict[str, Any],
    *,
    variant_index: int = 0,
    site: str | None = None,
    harmony_mode: str | None = None,
    user_prompt: str | None = None,
    palette_id: str | None = None,
) -> dict[str, Any]:
    """
    Build one website palette JSON document.

    Uses prompt brief for accent hue center, site profile for brand-lock / theme mode,
    and harmony geometry for Coolors-style arrangements.
    """
    profile = get_site_profile(site)
    site_key = normalize_site_id(site)
    mode = harmony_mode or str(profile.get("harmony_default", "analogous"))
    if mode not in HARMONY_MODES:
        mode = "analogous"

    ps = dict(genome.get("prompt_session") or {})
    if user_prompt:
        patch = genome_patch_from_prompt(user_prompt)
        ps.update(patch.get("prompt_session") or {})

    base_hue = float(ps.get("accent_hue_center", 210))
    theme_mode = str(profile.get("theme_mode", "dark"))
    if ps.get("prefer_light_ui") or "light" in str(ps.get("source_text", "")).lower():
        theme_mode = "light"

    sat_cfg = genome.get("saturation_profile", {})
    light_cfg = genome.get("lightness_profile", {})
    swatches = harmony_swatches(
        base_hue,
        mode,
        count=5,
        variant_index=variant_index,
        theme_mode=theme_mode,
        sat_base=tuple(sat_cfg.get("base_saturation", [10, 25])),
        sat_accent=tuple(sat_cfg.get("accent_saturation", [60, 85])),
        light_bg=float(light_cfg.get("background_range", [8, 18])[0]),
        light_fg=float(light_cfg.get("foreground_range", [85, 97])[1]),
        light_mid=sum(light_cfg.get("midtone_range", [40, 60])) / 2,
    )

    role_map = _swatches_to_role_map(swatches, profile, genome=genome)
    fg = role_map.get("foreground", swatches[-1])
    family = _nearest_family(base_hue)
    pid = palette_id or f"web_{site_key}_palette_{variant_index + 1:02d}"

    colors: list[dict[str, Any]] = []
    for role, hx in role_map.items():
        hsl_val: list[int] | None = list(hex_to_hsl(hx)) if hx.startswith("#") and len(hx.strip()) == 7 else None
        colors.append(
            {
                "role": role,
                "hex": hx,
                "hsl": hsl_val,
                "contrast_with_foreground": round(contrast_ratio(fg, hx), 2)
                if hx.startswith("#")
                else None,
                "contrast_with_background": round(contrast_ratio(hx, role_map.get("background", hx)), 2)
                if hx.startswith("#")
                else None,
                "genome_principles_applied": [
                    "web_pathway",
                    f"harmony_{mode}",
                    f"site_{site_key}",
                    f"hue_family_{family}",
                ],
                "rationale": f"{role} via {mode} harmony for {profile.get('label', site_key)}.",
            }
        )

    gc = {
        "harmony_mode": mode,
        "site": site_key,
        "theme_mode": theme_mode,
        "brand_lock": bool(profile.get("brand_lock")),
    }
    if ps.get("chromatic_variety") is not None:
        gc["chromatic_variety"] = ps["chromatic_variety"]
    if ps.get("prompt_adherence") is not None:
        gc["prompt_adherence"] = ps["prompt_adherence"]

    return {
        "id": pid,
        "context": "web",
        "site": site_key,
        "hue_family": family,
        "harmony_mode": mode,
        "taste_context": f"{site_key}:{mode}:{theme_mode}",
        "design_paradigms_applied": [
            "readability_first",
            "semantic_separation",
            "accent_as_wayfinding",
        ],
        "techniques_applied": [
            f"harmony_{mode}",
            "wcag_contrast_repair",
            "site_profile_" + site_key,
        ],
        "genome_version": genome.get("version", "1.1.0"),
        "generated": _iso_now(),
        "colors": colors,
        "harmony_swatches": swatches,
        "palette_rationale": (
            f"Web pathway: {describe_harmony(mode)} Site profile: {profile.get('label', site_key)}."
        ),
        "conflicts_flagged": _flag_contrast_issues(colors),
        "user_prompt": user_prompt,
        "generation_controls": gc,
    }


def describe_harmony(mode: str) -> str:
    from core.harmony import describe_harmony as _d

    return _d(mode)


def _flag_contrast_issues(colors: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for c in colors:
        role = c.get("role", "")
        ratio = c.get("contrast_with_background")
        if ratio is not None and role in ("foreground", "muted", "accent_primary") and ratio < 3.0:
            issues.append(f"{role}_low_contrast_vs_background")
    return issues


def generate_web_batch(
    genome: dict[str, Any],
    *,
    count: int,
    site: str | None,
    harmony_mode: str | None,
    user_prompt: str | None,
    output_dir: Any,
) -> list[dict[str, Any]]:
    """Write `count` web palette JSON files and return palette dicts."""
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    site_key = normalize_site_id(site)
    generated: list[dict[str, Any]] = []
    for i in range(count):
        pal = build_web_palette(
            genome,
            variant_index=i,
            site=site,
            harmony_mode=harmony_mode,
            user_prompt=user_prompt,
            palette_id=f"web_{site_key}_palette_{i + 1:02d}",
        )
        path = out / f"{pal['id']}.json"
        import json

        path.write_text(json.dumps(pal, indent=2), encoding="utf-8")
        generated.append(pal)
    return generated
