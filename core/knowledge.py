"""Compounding taste knowledge — ledger events + numeric priors.

Every keep/discard/iterate appends an event. Priors are recomputed from
kept canon palettes + ledger so later makes get better (not random).

Agents call: record_event → recompute_priors → apply_priors_to_session
Humans control: keep (compound) vs discard (negative signal) vs set_role.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.layout import knowledge_dir, LEDGER_FILENAME, PRIORS_FILENAME
from core.math_engine import hex_to_hsl
from core.sku import normalize_slug

ROLES = (
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
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ledger_path(root: Path) -> Path:
    return knowledge_dir(root) / LEDGER_FILENAME


def priors_path(root: Path) -> Path:
    return knowledge_dir(root) / PRIORS_FILENAME


def role_map(palette: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in palette.get("colors") or []:
        role, hx = c.get("role"), c.get("hex")
        if role and hx:
            out[str(role)] = str(hx)
    return out


def _circular_mean(hues: list[float]) -> float | None:
    if not hues:
        return None
    s = sum(math.sin(math.radians(h)) for h in hues)
    c = sum(math.cos(math.radians(h)) for h in hues)
    if s == 0 and c == 0:
        return hues[0]
    return math.degrees(math.atan2(s, c)) % 360.0


def _hue_delta(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def palette_signature(palette: dict[str, Any]) -> dict[str, Any]:
    """Compact compounding unit extracted from a palette JSON."""
    roles = role_map(palette)
    accent = roles.get("accent_primary") or roles.get("foreground", "#888888")
    bg = roles.get("background", "#111111")
    ah, as_, al = hex_to_hsl(accent)
    bh, bs, bl = hex_to_hsl(bg)
    syntax_hues = []
    for i in range(1, 7):
        hx = roles.get(f"syntax_{i}")
        if hx:
            syntax_hues.append(hex_to_hsl(hx)[0])
    slug = normalize_slug(str(palette.get("style_archetype") or ""))
    return {
        "palette_id": palette.get("id"),
        "slug": slug,
        "is_light": bool(palette.get("is_light")),
        "roles": roles,
        "accent_hue": float(ah),
        "accent_sat": float(as_),
        "accent_light": float(al),
        "bg_hue": float(bh),
        "bg_sat": float(bs),
        "bg_light": float(bl),
        "syntax_hues": syntax_hues,
        "syntax_spread": (max(syntax_hues) - min(syntax_hues)) if len(syntax_hues) >= 2 else 0.0,
        "display": palette.get("theme_display_name") or palette.get("theme_name"),
        "prompt": palette.get("user_prompt"),
    }


def append_ledger(root: Path, event: dict[str, Any]) -> None:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"at": _iso_now(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_ledger(root: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = ledger_path(root)
    if not path.is_file():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if limit:
        lines = lines[-limit:]
    return [json.loads(ln) for ln in lines]


def load_priors(root: Path) -> dict[str, Any]:
    path = priors_path(root)
    if not path.is_file():
        return empty_priors()
    return json.loads(path.read_text(encoding="utf-8"))


def empty_priors() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "canon_count": 0,
        "keep_count": 0,
        "discard_count": 0,
        "dark": {},
        "light": {},
        "occupied_accents": [],
        "slugs": [],
        "neighbor_index": [],
    }


def _mode_bucket(sigs: list[dict[str, Any]], is_light: bool) -> dict[str, Any]:
    subset = [s for s in sigs if s["is_light"] is is_light]
    if not subset:
        return {}
    accents = [s["accent_hue"] for s in subset]
    bg_l = [s["bg_light"] for s in subset]
    bg_s = [s["bg_sat"] for s in subset]
    acc_s = [s["accent_sat"] for s in subset]
    spreads = [s["syntax_spread"] for s in subset]
    return {
        "count": len(subset),
        "accent_hue_center": round(_circular_mean(accents) or 0.0, 2),
        "accent_hues": [round(h, 1) for h in accents],
        "bg_light_mean": round(sum(bg_l) / len(bg_l), 2),
        "bg_light_range": [round(min(bg_l), 1), round(max(bg_l), 1)],
        "bg_sat_mean": round(sum(bg_s) / len(bg_s), 2),
        "accent_sat_mean": round(sum(acc_s) / len(acc_s), 2),
        "syntax_spread_mean": round(sum(spreads) / len(spreads), 2),
        "slugs": [s["slug"] for s in subset if s.get("slug")],
    }


def recompute_priors(root: Path, canon_palettes: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild numeric priors from kept canon + ledger stats. This is the compound step."""
    sigs = [palette_signature(p) for p in canon_palettes]
    ledger = read_ledger(root)
    keep_n = sum(1 for e in ledger if e.get("type") in ("keep", "keep_replace"))
    discard_n = sum(1 for e in ledger if e.get("type") == "discard")

    # Negative learning: discarded accent hues get a novelty push (avoid repeating mistakes)
    avoided: list[float] = []
    for e in ledger:
        if e.get("type") == "discard" and e.get("accent_hue") is not None:
            avoided.append(float(e["accent_hue"]))

    priors = {
        "version": 2,
        "updated_at": _iso_now(),
        "canon_count": len(sigs),
        "keep_count": keep_n,
        "discard_count": discard_n,
        "dark": _mode_bucket(sigs, False),
        "light": _mode_bucket(sigs, True),
        "occupied_accents": [
            {"slug": s["slug"], "hue": round(s["accent_hue"], 1), "is_light": s["is_light"]}
            for s in sigs
        ],
        "avoided_accents": [round(h, 1) for h in avoided[-40:]],
        "slugs": [s["slug"] for s in sigs if s.get("slug")],
        "neighbor_index": [
            {
                "slug": s["slug"],
                "palette_id": s["palette_id"],
                "is_light": s["is_light"],
                "accent_hue": round(s["accent_hue"], 1),
                "bg_light": s["bg_light"],
                "bg_sat": s["bg_sat"],
                "accent_sat": s["accent_sat"],
                "syntax_spread": s["syntax_spread"],
                "roles": s["roles"],
            }
            for s in sigs
        ],
    }
    path = priors_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(priors, indent=2) + "\n", encoding="utf-8")
    return priors


def nearest_neighbors(
    priors: dict[str, Any],
    *,
    accent_hue: float,
    is_light: bool,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Rank canon signatures for seeding a new make."""
    idx = list(priors.get("neighbor_index") or [])
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in idx:
        mode_pen = 0.0 if row.get("is_light") is is_light else 40.0
        dist = _hue_delta(float(row["accent_hue"]), accent_hue) + mode_pen
        scored.append((dist, row))
    scored.sort(key=lambda t: t[0])
    return [row for _, row in scored[:k]]


def novelty_penalty(priors: dict[str, Any], accent_hue: float, *, is_light: bool, min_sep: float = 18.0) -> float:
    """0 = free space, 1 = sitting on an existing kept accent (or discarded one)."""
    worst = 0.0
    for row in priors.get("occupied_accents") or []:
        if row.get("is_light") is not is_light:
            continue
        d = _hue_delta(float(row["hue"]), accent_hue)
        if d < min_sep:
            worst = max(worst, 1.0 - d / min_sep)
    for h in priors.get("avoided_accents") or []:
        d = _hue_delta(float(h), accent_hue)
        if d < min_sep:
            worst = max(worst, 0.7 * (1.0 - d / min_sep))
    return worst


def nudge_accent_for_novelty(
    priors: dict[str, Any],
    accent_hue: float,
    *,
    is_light: bool,
    min_sep: float = 18.0,
) -> float:
    """Walk accent hue until clear of occupied/avoided bands."""
    hue = accent_hue % 360.0
    for step in range(0, 36):
        trial = (hue + step * 7.0) % 360.0
        if novelty_penalty(priors, trial, is_light=is_light, min_sep=min_sep) < 0.25:
            return trial
        trial = (hue - step * 7.0) % 360.0
        if novelty_penalty(priors, trial, is_light=is_light, min_sep=min_sep) < 0.25:
            return trial
    return hue


def apply_priors_to_session(
    genome: dict[str, Any],
    priors: dict[str, Any],
    *,
    accent_hue: float | None,
    is_light: bool,
    variety: float,
    adherence: float,
) -> dict[str, Any]:
    """Wire compounding priors into the knobs generate.py actually reads."""
    mode = priors.get("light" if is_light else "dark") or {}
    ps = genome.setdefault("prompt_session", {})
    ps["chromatic_variety"] = variety
    ps["prompt_adherence"] = adherence
    if accent_hue is not None:
        # Blend prompt intent with mode center from kept winners
        center = mode.get("accent_hue_center")
        if center is not None and adherence < 0.95:
            # Low adherence → lean on canon center; high → lock to prompt
            w = 0.15 + 0.75 * adherence
            # shortest-arc lerp
            a, b = float(center), float(accent_hue)
            d = ((b - a + 540) % 360) - 180
            blended = (a + d * w) % 360
        else:
            blended = float(accent_hue)
        blended = nudge_accent_for_novelty(priors, blended, is_light=is_light)
        ps["accent_hue_center"] = round(blended, 2)
        ps["accent_hue_spread"] = 10.0 + 14.0 * (1.0 - adherence)
        ps["compounding"] = {
            "canon_count": priors.get("canon_count", 0),
            "mode_count": mode.get("count", 0),
            "novelty_nudge": True,
        }

    if mode:
        bg_mean = mode.get("bg_light_mean")
        bg_range = mode.get("bg_light_range")
        if bg_range and len(bg_range) == 2:
            genome["lightness_profile"] = {
                **genome.get("lightness_profile", {}),
                "background_range": list(bg_range),
                "notes": "Compounded from kept canon of matching theme mode.",
            }
        acc_sat = mode.get("accent_sat_mean")
        if acc_sat is not None:
            lo = max(40, acc_sat - 12)
            hi = min(95, acc_sat + 12)
            genome["saturation_profile"] = {
                **genome.get("saturation_profile", {}),
                "accent_saturation": [lo, hi],
                "notes": "Compounded accent chroma from kept winners.",
            }
    return genome


def record_keep(
    root: Path,
    palette: dict[str, Any],
    *,
    prompt: str | None = None,
    replaces: str | None = None,
) -> None:
    sig = palette_signature(palette)
    entry: dict[str, Any] = {
        "type": "keep",
        "palette_id": sig["palette_id"],
        "slug": sig["slug"],
        "is_light": sig["is_light"],
        "accent_hue": sig["accent_hue"],
        "prompt": prompt or sig.get("prompt"),
        "roles": sig["roles"],
    }
    if replaces:
        entry["replaces"] = replaces
        entry["type"] = "keep_replace"
    append_ledger(root, entry)


def record_discard(root: Path, palette: dict[str, Any], *, prompt: str | None = None) -> None:
    sig = palette_signature(palette)
    append_ledger(
        root,
        {
            "type": "discard",
            "palette_id": sig["palette_id"],
            "slug": sig.get("slug"),
            "is_light": sig["is_light"],
            "accent_hue": sig["accent_hue"],
            "prompt": prompt or sig.get("prompt"),
        },
    )


def record_iterate(
    root: Path,
    *,
    parent_id: str | None,
    child_id: str,
    prompt: str,
    accent_hue: float | None = None,
) -> None:
    append_ledger(
        root,
        {
            "type": "iterate",
            "parent_id": parent_id,
            "palette_id": child_id,
            "prompt": prompt,
            "accent_hue": accent_hue,
        },
    )
