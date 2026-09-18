"""Compound palette generation — seed from kept neighbors + priors, then math.

New themes are not blank rolls. They inherit structural DNA (bg ladder, sat,
syntax spread) from nearest kept winners, then lock accent to the brief with
novelty separation so each keep expands useful taste space.
"""

from __future__ import annotations

from typing import Any

from core.knowledge import nearest_neighbors, novelty_penalty
from core.math_engine import contrast_ratio, hex_to_hsl, hsl_to_hex
from core.prompt_brief import ACCENT_HUES, DARK_WORDS, LIGHT_WORDS, _tokens
from core.sku import display_to_slug, normalize_slug, slug_to_display


def parse_brief(prompt: str) -> dict[str, Any]:
    """Extract light/dark + accent hue + optional explicit slug from a chat brief."""
    raw = prompt.strip()
    tl = raw.lower()
    tokens = set(_tokens(raw))

    is_light: bool | None = None
    if tokens & LIGHT_WORDS and not (tokens & DARK_WORDS):
        is_light = True
    elif tokens & DARK_WORDS:
        is_light = False

    accents: list[tuple[str, float]] = []
    for word, hue in ACCENT_HUES.items():
        if word in tokens:
            accents.append((word, hue))
    accents.sort(key=lambda wh: next((i for i, t in enumerate(_tokens(raw)) if t == wh[0]), 999))

    # Explicit "RR Name" or known slug mention
    explicit_slug = None
    if "rr " in tl or raw.lower().startswith("rr"):
        # try last title-ish phrase
        pass

    return {
        "prompt": raw,
        "is_light": is_light,
        "accent_word": accents[0][0] if accents else None,
        "accent_hue": accents[0][1] if accents else None,
        "accent_words": [a[0] for a in accents],
        "explicit_slug": explicit_slug,
    }


def invent_slug(prompt: str, *, accent_word: str | None, is_light: bool) -> str:
    """Create a fresh display-aligned slug for a new generative theme."""
    # Prefer color word + mood noun
    mood = "paper" if is_light else "night"
    for token, noun in (
        ("purple", "violet"),
        ("violet", "violet"),
        ("magenta", "magenta"),
        ("indigo", "indigo"),
        ("lavender", "lavender"),
        ("plum", "plum"),
    ):
        if token in prompt.lower():
            base = noun
            break
    else:
        base = accent_word or ("haze" if is_light else "ember")

    # Distinct two-word RR names
    if is_light:
        pairs = {
            "violet": "violet_mist",
            "purple": "violet_mist",
            "magenta": "magenta_foam",
            "indigo": "indigo_veil",
            "lavender": "lavender_paper",
            "plum": "plum_cream",
        }
    else:
        pairs = {
            "violet": "violet_nocturne",
            "purple": "violet_nocturne",
            "magenta": "magenta_signal",
            "indigo": "indigo_abyss",
            "lavender": "lavender_void",
            "plum": "plum_ember",
        }
    slug = pairs.get(base) or f"{base}_{mood}"
    return normalize_slug(slug)


FORK_SLUG_CANDIDATES: list[tuple[tuple[str, ...], str]] = [
    (("twilight lake", "lake twilight", "lake at dusk"), "twilight_lake"),
    (("twilight", "dusk", "lake", "sunset"), "periwinkle_twilight"),
    (("periwinkle",), "periwinkle_twilight"),
    (("lilac",), "lilac_dusk"),
    (("lavender",), "lavender_dusk"),
    (("indigo",), "indigo_veil"),
    (("plum",), "plum_cream"),
    (("magenta",), "magenta_foam"),
    (("purple", "violet"), "violet_haze"),
]


def invent_fork_slug(
    prompt: str,
    *,
    parent_slug: str | None,
    is_light: bool,
    known_slugs: set[str] | frozenset[str],
) -> str:
    """New SKU slug for fork-iterate — sibling of parent, never collides with canon."""
    text = prompt.lower()
    for keywords, slug in FORK_SLUG_CANDIDATES:
        if any(k in text for k in keywords):
            candidate = normalize_slug(slug)
            if candidate not in known_slugs and candidate != parent_slug:
                return candidate
    # Default: parent mood + variant suffix
    base = (parent_slug or "violet").removesuffix("_mist").removesuffix("_night")
    for suffix in ("twilight", "dusk", "haze", "veil", "glow", "paper"):
        candidate = normalize_slug(f"{base}_{suffix}")
        if candidate not in known_slugs and candidate != parent_slug:
            return candidate
    return normalize_slug(invent_slug(prompt, accent_word="violet", is_light=is_light))


def resolve_generation_plan(
    prompt: str,
    priors: dict[str, Any],
    *,
    style: str | None = None,
    is_light: bool | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    brief = parse_brief(prompt)
    light = is_light if is_light is not None else brief["is_light"]
    if light is None:
        # Default dark when unspecified — matches product bias
        light = False

    accent = brief["accent_hue"]
    if accent is None and style:
        # fall back to nearest slug's accent if asking for existing SKU
        for row in priors.get("neighbor_index") or []:
            if row.get("slug") == normalize_slug(style):
                accent = float(row["accent_hue"])
                light = bool(row["is_light"]) if is_light is None else light
                break
    if accent is None:
        mode = priors.get("light" if light else "dark") or {}
        accent = float(mode.get("accent_hue_center") or (280 if not light else 210))

    slug = normalize_slug(style) if style else None
    known = {row.get("slug") for row in (priors.get("neighbor_index") or [])}
    is_existing_sku = bool(slug and slug in known)

    if name:
        slug = display_to_slug(name)
    elif not slug or not is_existing_sku:
        # New generative theme — invent display-aligned slug from brief
        slug = invent_slug(prompt, accent_word=brief["accent_word"], is_light=light)

    neighbors = nearest_neighbors(priors, accent_hue=float(accent), is_light=light, k=3)
    novelty = novelty_penalty(priors, float(accent), is_light=light)

    return {
        "slug": slug,
        "display": slug_to_display(slug),
        "is_light": light,
        "accent_hue": float(accent),
        "accent_word": brief["accent_word"],
        "is_existing_sku": is_existing_sku,
        "neighbors": neighbors,
        "novelty": novelty,
        "brief": brief,
    }


def seed_roles_from_neighbors(
    neighbors: list[dict[str, Any]],
    *,
    accent_hue: float,
    is_light: bool,
    variety: float,
) -> dict[str, str] | None:
    """Blend neighbor role hexes into a structural seed (before math polish)."""
    if not neighbors:
        return None
    # Primary neighbor donates chrome structure; accent replaced
    primary = neighbors[0].get("roles") or {}
    if not primary.get("background"):
        return None

    seed = dict(primary)
    # Shift accents toward target hue, keep sat/light from primary accent
    for role in ("accent_primary", "accent_secondary"):
        hx = seed.get(role)
        if not hx:
            continue
        _h, s, l = hex_to_hsl(hx)
        shift = 0 if role == "accent_primary" else (18 + 20 * variety)
        seed[role] = hsl_to_hex((accent_hue + shift) % 360, s, l)

    # Soft-blend bg lightness toward mean of neighbors (same mode)
    bg_lights = []
    for n in neighbors:
        roles = n.get("roles") or {}
        if roles.get("background"):
            bg_lights.append(hex_to_hsl(roles["background"])[2])
    if bg_lights and seed.get("background"):
        h, s, _l = hex_to_hsl(seed["background"])
        target_l = sum(bg_lights) / len(bg_lights)
        # Keep mode constraints
        if is_light:
            target_l = max(88, min(97, target_l))
        else:
            target_l = max(4, min(22, target_l))
        seed["background"] = hsl_to_hex(h, min(s, 18 if not is_light else 12), target_l)

    fg = "#1A1A1A" if is_light else "#FAFAFA"
    if seed.get("background"):
        seed["foreground"] = fg
        if contrast_ratio(fg, seed["background"]) < 7.0:
            seed["foreground"] = "#111111" if is_light else "#FFFFFF"
    return seed
