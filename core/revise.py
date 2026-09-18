"""Revise a kept/draft palette from feedback — used by iterate.

Kept SKUs must remain iterable: start from parent role hexes, nudge by prompt,
never freeze-reload canon. DNA only updates on keep (which may supersede).
"""

from __future__ import annotations

from typing import Any

from core.math_engine import contrast_ratio, hex_to_hsl, hsl_to_hex
from core.prompt_brief import ACCENT_HUES, _tokens

CHROME_ROLES = ("background", "surface", "border", "muted")
ACCENT_ROLES = ("accent_primary", "accent_secondary")
SYNTAX_ROLES = tuple(f"syntax_{i}" for i in range(1, 7))

MORE_WORDS = frozenset(
    {"more", "stronger", "deeper", "richer", "punchier", "vivid", "brighter", "hazier", "washier"}
)
LESS_WORDS = frozenset({"less", "softer", "subtle", "calmer", "muted", "quieter", "duller"})
HAZE_WORDS = frozenset(
    {"haze", "haziness", "wash", "washed", "fog", "mist", "tint", "tinted", "lavender", "lilac"}
)
PURPLE_WORDS = frozenset({"purple", "violet", "lavender", "lilac", "plum", "magenta", "periwinkle", "indigo"})
RICH_PURPLE_WORDS = frozenset(
    {"shade", "shades", "spectrum", "gradient", "twilight", "dusk", "atmospheric", "reference", "picture", "photo"}
)
FORK_WORDS = frozenset(
    {"alongside", "separate", "second", "another", "new one", "new theme", "fork", "sibling", "variant", "also keep"}
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _shift_hex(hx: str, *, dh: float = 0.0, ds: float = 0.0, dl: float = 0.0) -> str:
    h, s, l = hex_to_hsl(hx)
    return hsl_to_hex((h + dh) % 360, _clamp(s + ds, 0, 100), _clamp(l + dl, 2, 98))


def _feedback_axes(prompt: str) -> dict[str, float]:
    """Map free-text feedback into sat/light/hue nudge strengths."""
    text = prompt.lower()
    tokens = set(text.replace("-", " ").split())
    more = bool(tokens & MORE_WORDS) or "more " in text
    less = bool(tokens & LESS_WORDS) or "less " in text
    haze = bool(tokens & HAZE_WORDS) or any(w in text for w in HAZE_WORDS)
    purple = bool(tokens & PURPLE_WORDS) or any(w in text for w in PURPLE_WORDS)

    direction = 0.0
    if more and not less:
        direction = 1.0
    elif less and not more:
        direction = -1.0
    elif more and less:
        direction = 0.35  # mixed → mild push toward "more X, less Y" handled below

    chrome_sat = 0.0
    chrome_light = 0.0
    accent_sat = 0.0
    hue_pull = 0.0
    hue_lock = 0.0

    # Named color words lock iterate toward that hue (lime 95°, azure 210°, …)
    for tok in _tokens(prompt):
        if tok in ACCENT_HUES:
            hue_pull = float(ACCENT_HUES[tok])
            hue_lock = 0.55
            break

    if haze or purple:
        # Chrome wash: sat up for haze, slight light lift on paper
        chrome_sat = (10.0 if direction >= 0 else -8.0) * (1.0 if direction != 0 else 0.7)
        if direction >= 0:
            chrome_light = 1.5
        else:
            chrome_light = -1.0
        if purple and not hue_lock:
            hue_pull = 275.0  # soft pull toward violet

    if "brighter" in text or "punchier" in text or "vivid" in text:
        accent_sat += 8.0 * (1.0 if direction >= 0 else -0.5)
        chrome_sat += 3.0
    if "softer" in text or "calmer" in text or "subtle" in text:
        accent_sat -= 6.0
        chrome_sat -= 4.0

    if direction == 0 and not (haze or purple):
        # Generic iterate with no strong keywords — still move slightly so drafts differ
        chrome_sat = 4.0
        accent_sat = 2.0

    return {
        "chrome_sat": chrome_sat,
        "chrome_light": chrome_light,
        "accent_sat": accent_sat,
        "hue_pull": hue_pull,
        "hue_lock": hue_lock,
        "direction": direction,
    }


def wants_rich_purple_shades(prompt: str) -> bool:
    """True when the brief asks for a wide purple/lilac/periwinkle range."""
    text = prompt.lower()
    tokens = set(text.replace("-", " ").split())
    purple = bool(tokens & PURPLE_WORDS) or any(w in text for w in PURPLE_WORDS)
    rich = bool(tokens & RICH_PURPLE_WORDS) or "way more" in text or "many " in text
    return purple and rich


def detect_fork_intent(prompt: str) -> bool:
    """True when user wants a sibling SKU, not a revision of the same slug."""
    text = prompt.lower()
    if any(phrase in text for phrase in FORK_WORDS):
        return True
    # "keep X but iterate" / "don't replace" patterns
    if "keep" in text and any(w in text for w in ("iterate", "new", "second", "another", "fork")):
        return True
    if "don't replace" in text or "do not replace" in text or "not replace" in text:
        return True
    return False


def build_rich_purple_roles(
    *,
    is_light: bool,
    prompt: str,
    parent_roles: dict[str, str] | None = None,
) -> dict[str, str]:
    """Multi-shade purple ladder — twilight lake / periwinkle haze (light theme).

    Chrome spans lilac-white paper → periwinkle mist → indigo-plum ink.
    Syntax spans indigo, periwinkle, lilac, plum, magenta-violet, dusty purple.
    """
    if not is_light:
        return build_rich_purple_roles_dark(prompt, parent_roles)

    # Light: lifted from pale glowing cloud through misty water to silhouette ink
    roles = {
        "background": "#EAE6F8",
        "surface": "#DDD6F2",
        "border": "#C4B8E4",
        "muted": "#8E84B8",
        "foreground": "#2D2450",
        "accent_primary": "#6E5FD4",
        "accent_secondary": "#9588E8",
        "syntax_1": "#5B4FC9",
        "syntax_2": "#7B6FD8",
        "syntax_3": "#9D8FE8",
        "syntax_4": "#4A3D9E",
        "syntax_5": "#B088E0",
        "syntax_6": "#6A5AAA",
    }
    text = prompt.lower()
    if "twilight" in text or "dusk" in text or "lake" in text:
        # Slightly cooler / bluer periwinkle pull (matches reference photo)
        for role in ("background", "surface", "border"):
            h, s, l = hex_to_hsl(roles[role])
            roles[role] = hsl_to_hex((h - 6) % 360, _clamp(s + 4, 0, 72), l)
        for role in SYNTAX_ROLES:
            h, s, l = hex_to_hsl(roles[role])
            roles[role] = hsl_to_hex((h - 4) % 360, s, l)

    if parent_roles:
        # Blend chrome lightness toward parent so fork feels related, not alien
        for role in CHROME_ROLES:
            if role not in parent_roles:
                continue
            ph, ps, pl = hex_to_hsl(parent_roles[role])
            h, s, l = hex_to_hsl(roles[role])
            roles[role] = hsl_to_hex(h, int((s + ps) / 2), int((l + pl) / 2))

    fg, bg = roles["foreground"], roles["background"]
    if contrast_ratio(fg, bg) < 7.0:
        roles["foreground"] = "#231C42"
    return roles


def wants_rich_purple_shades(prompt: str) -> bool:
    """True when the brief asks for a wide purple/lilac/periwinkle range."""
    text = prompt.lower()
    tokens = set(text.replace("-", " ").split())
    purple = bool(tokens & PURPLE_WORDS) or any(w in text for w in PURPLE_WORDS)
    rich = (
        bool(tokens & RICH_PURPLE_WORDS)
        or "way more" in text
        or "many " in text
        or "powerful" in text
        or "reference" in text
        or "picture" in text
        or "photo" in text
        or "scheme" in text
    )
    atmospheric = any(w in text for w in ("twilight", "dusk", "lake", "mist", "haze"))
    return purple and (rich or atmospheric)


def build_rich_purple_roles_dark(
    prompt: str,
    parent_roles: dict[str, str] | None = None,
) -> dict[str, str]:
    """Dark twilight-lake reference — indigo depth + luminous periwinkle/lilac glow."""
    _ = parent_roles
    text = prompt.lower()
    twilight_ref = any(w in text for w in ("twilight", "dusk", "lake", "reference", "picture", "photo"))

    if twilight_ref:
        # Mapped from ref: cloud ink, silhouette plum, misty periwinkle, lilac glow on water
        roles = {
            "background": "#0E0D18",
            "surface": "#181628",
            "border": "#2E2848",
            "muted": "#5E5888",
            "foreground": "#E6E2F5",
            "accent_primary": "#A094F0",
            "accent_secondary": "#CBBFF8",
            "syntax_1": "#9588E8",
            "syntax_2": "#B8AEF5",
            "syntax_3": "#6B5FD4",
            "syntax_4": "#E8E2FF",
            "syntax_5": "#4A4088",
            "syntax_6": "#7E74C8",
        }
    else:
        roles = {
            "background": "#1A1830",
            "surface": "#252240",
            "border": "#3D3560",
            "muted": "#6B6298",
            "foreground": "#EDE8F8",
            "accent_primary": "#9588E8",
            "accent_secondary": "#B088E0",
            "syntax_1": "#7B6FD8",
            "syntax_2": "#9D8FE8",
            "syntax_3": "#5B4FC9",
            "syntax_4": "#B088E0",
            "syntax_5": "#4A3D9E",
            "syntax_6": "#6A5AAA",
        }

    fg, bg = roles["foreground"], roles["background"]
    if contrast_ratio(fg, bg) < 7.0:
        roles["foreground"] = "#F0ECFA"
    return roles


def nudge_roles_from_feedback(
    roles: dict[str, str],
    prompt: str,
    *,
    is_light: bool,
    variety: float = 0.55,
) -> dict[str, str]:
    """Return a new role→hex map derived from parent roles + feedback."""
    axes = _feedback_axes(prompt)
    scale = 0.75 + 0.5 * float(variety)
    out = dict(roles)

    for role in CHROME_ROLES:
        hx = out.get(role)
        if not hx:
            continue
        ds = axes["chrome_sat"] * scale
        dl = axes["chrome_light"] * scale
        if role == "border":
            ds *= 1.15
        if role == "muted":
            ds *= 0.9
            dl *= 0.5
        # Keep light themes in paper band; dark in ink band
        h, s, l = hex_to_hsl(hx)
        if axes["hue_pull"]:
            target = axes["hue_pull"]
            blend = 0.42 if axes.get("hue_lock") else 0.18
            d = ((target - h + 540) % 360) - 180
            h = (h + d * blend) % 360
        new_l = _clamp(l + dl, 88 if is_light else 4, 98 if is_light else 28)
        if role == "muted":
            new_l = _clamp(l + dl, 35 if is_light else 28, 62 if is_light else 55)
        new_s = _clamp(s + ds, 2 if is_light else 4, 72 if is_light else 45)
        out[role] = hsl_to_hex(h, new_s, new_l)

    for role in ACCENT_ROLES:
        hx = out.get(role)
        if not hx:
            continue
        h, s, l = hex_to_hsl(hx)
        if axes["hue_pull"]:
            target = axes["hue_pull"]
            blend = float(axes.get("hue_lock") or 0.08)
            d = ((target - h + 540) % 360) - 180
            h = (h + d * blend) % 360
        if role == "accent_secondary":
            h = (h + 8) % 360
        out[role] = hsl_to_hex(h, _clamp(s + axes["accent_sat"] * scale, 35, 95), l)

    for role in SYNTAX_ROLES:
        hx = out.get(role)
        if not hx:
            continue
        ds = axes["accent_sat"] * 0.35 * scale
        dh = 0.0
        if axes["hue_pull"] and axes.get("hue_lock"):
            h, _s, _l = hex_to_hsl(hx)
            target = axes["hue_pull"]
            d = ((target - h + 540) % 360) - 180
            dh = d * 0.28
        out[role] = _shift_hex(hx, dh=dh, ds=ds)

    fg = out.get("foreground")
    bg = out.get("background")
    if fg and bg:
        h, s, l = hex_to_hsl(fg)
        if axes["hue_pull"]:
            target = axes["hue_pull"]
            d = ((target - h + 540) % 360) - 180
            h = (h + d * 0.12) % 360
        # Ensure readable ink
        target_l = 16 if is_light else 94
        out["foreground"] = hsl_to_hex(h, _clamp(s + 2, 8, 40), target_l)
        if contrast_ratio(out["foreground"], bg) < 7.0:
            out["foreground"] = hsl_to_hex(h, _clamp(s + 4, 10, 45), 12 if is_light else 96)

    return out


def colors_from_roles(roles: dict[str, str], *, principles: list[str] | None = None) -> list[dict[str, Any]]:
    """Build palette color entries from a role hex map."""
    bg = roles.get("background", "#111111")
    fg = roles.get("foreground", "#FAFAFA")
    order = [
        "background",
        "surface",
        "border",
        "muted",
        "foreground",
        "accent_primary",
        "accent_secondary",
        *SYNTAX_ROLES,
    ]
    tags = principles or ["revised_from_parent", "feedback_nudge"]
    out: list[dict[str, Any]] = []
    for role in order:
        hx = roles.get(role)
        if not hx:
            continue
        out.append(
            {
                "role": role,
                "hex": hx,
                "hsl": list(hex_to_hsl(hx)),
                "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
                "contrast_with_background": round(contrast_ratio(hx, bg), 2),
                "genome_principles_applied": list(tags),
                "rationale": f"{role} revised from parent via feedback nudge.",
            }
        )
    return out
