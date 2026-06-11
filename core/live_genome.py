"""Dynamic genome layer: roster palette colors, features, and interrelationships."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from core.genome import merge_genomes
from core.ide_iteration import ship_palette_ids
from core.ide_schema import enrich_legacy_palette, palette_meta
from core.layout import registry_dir
from core.math_engine import hex_to_hsl
from core.roster import load_roster


def _role_map(palette: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in palette.get("colors", []):
        role = c.get("role")
        hx = c.get("hex")
        if role and hx:
            out[str(role)] = str(hx)
    return out


def _hue(hex_color: str) -> float:
    h, _s, _l = hex_to_hsl(hex_color)
    return float(h)


def _lightness(hex_color: str) -> float:
    _h, _s, l = hex_to_hsl(hex_color)
    return float(l)


def _hue_delta(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _circular_mean_hue(hues: list[float]) -> float | None:
    if not hues:
        return None
    import math

    sin_sum = sum(math.sin(math.radians(h)) for h in hues)
    cos_sum = sum(math.cos(math.radians(h)) for h in hues)
    if sin_sum == 0 and cos_sum == 0:
        return hues[0]
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0


def extract_palette_features(palette: dict[str, Any]) -> dict[str, Any]:
    """Per-palette color signature for the live layer."""
    palette = enrich_legacy_palette(palette)
    roles = _role_map(palette)
    meta = palette_meta(palette)
    accent = roles.get("accent_primary") or roles.get("accent_secondary") or roles.get("foreground", "#888888")
    bg = roles.get("background", "#111111")
    syntax_hues = [
        _hue(roles[f"syntax_{i}"])
        for i in range(1, 7)
        if roles.get(f"syntax_{i}")
    ]
    return {
        "palette_id": palette.get("id", ""),
        "style_archetype": meta["style_archetype"],
        "is_light": meta["is_light"],
        "hue_family": palette.get("hue_family"),
        "roles": roles,
        "accent_hue": _hue(accent),
        "bg_lightness": _lightness(bg),
        "syntax_hues": syntax_hues,
        "syntax_spread": max(syntax_hues) - min(syntax_hues) if len(syntax_hues) >= 2 else 0.0,
    }


def _relationship(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "a": a["palette_id"],
        "b": b["palette_id"],
        "hue_delta": round(_hue_delta(a["accent_hue"], b["accent_hue"]), 2),
        "same_family": a.get("hue_family") == b.get("hue_family") and bool(a.get("hue_family")),
        "mode_pair": f"{a['is_light']}|{b['is_light']}",
    }


def build_roster_live_layer(root: Path, palette_ids: list[str] | None = None) -> dict[str, Any] | None:
    """
    Compute features + edges across kept/draft palettes.
    Nothing is written to genome_v1.json — this is ephemeral synthesis.
    """
    reg = registry_dir(root)
    roster = load_roster(reg)
    ids = palette_ids or ship_palette_ids(root) or list(roster.get("palette_ids") or [])
    if not ids:
        return None

    palette_dir = root / "outputs" / "palettes"
    features: dict[str, dict[str, Any]] = {}
    for pid in ids:
        path = palette_dir / f"{pid}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        feat = extract_palette_features(payload)
        features[feat["palette_id"]] = feat

    if not features:
        return None

    ordered = [features[pid] for pid in ids if pid in features]
    edges: list[dict[str, Any]] = []
    for i, fa in enumerate(ordered):
        for fb in ordered[i + 1 :]:
            edges.append(_relationship(fa, fb))

    accent_hues = [f["accent_hue"] for f in ordered]
    families = Counter(str(f.get("hue_family") or "") for f in ordered if f.get("hue_family"))
    styles = [f["style_archetype"] for f in ordered]
    light_count = sum(1 for f in ordered if f["is_light"])

    return {
        "palette_ids": [f["palette_id"] for f in ordered],
        "features": {f["palette_id"]: f for f in ordered},
        "relationships": edges,
        "synthesis": {
            "accent_hue_center": _circular_mean_hue(accent_hues),
            "dominant_hue_families": [f for f, _ in families.most_common(3)],
            "style_archetypes": list(dict.fromkeys(styles)),
            "light_palette_ratio": round(light_count / len(ordered), 3),
            "pair_count": len(edges),
        },
    }


def apply_live_genome(base: dict[str, Any], root: Path) -> dict[str, Any]:
    """Merge static genome with dynamic roster color graph (in-memory only)."""
    layer = build_roster_live_layer(root)
    if not layer:
        return base

    syn = layer["synthesis"]
    patches: dict[str, Any] = {"roster_live": layer}

    center = syn.get("accent_hue_center")
    if center is not None:
        span = 28
        lo = int((center - span) % 360)
        hi = int((center + span) % 360)
        patches["hue_strategy"] = {
            "accent_hue_center": round(center, 2),
            "accent_hue_range": sorted([lo, hi]),
            "notes": "Derived from roster palette accent hues (live layer).",
        }

    styles = syn.get("style_archetypes") or []
    if styles:
        existing = list((base.get("style_archetypes") or {}).get("ide") or [])
        tail = [s for s in existing if s not in styles]
        patches["style_archetypes"] = {"ide": styles + tail}

    merged, _ = merge_genomes(base, patches)
    return merged
