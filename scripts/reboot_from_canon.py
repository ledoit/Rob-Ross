"""Nuke stale DNA and reboot knowledge/genome from kept live palettes only.

Run from repo root:
    python scripts/reboot_from_canon.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ide_theme import finalize_ide_themes
from core.knowledge import append_ledger, recompute_priors, role_map
from core.layout import genome_path, knowledge_dir, registry_dir
from core.math_engine import hex_to_hsl
from core.sku import LEGACY_SLUG_ALIASES, display_to_slug, normalize_slug, save_skus, slug_to_display

# Product tiers — keyed by canonical display slug
FREE_SLUGS = [
    "fjord_hammer",
    "alpenglow_paper",
    "lemon_haze",
    "forest_canopy",
    "night_siren",
    "kimbie_warm",
]
PRO_SLUGS = [
    "sky_azure",
    "lemon_custard",
    "cherry_cream",
    "high_contrast_signal",
]

# Themes with locked hand-authored hex (do not math-regenerate on make-by-name)
CURATED_SLUGS = {
    "lemon_haze",
    "lemon_custard",
    "cherry_cream",
    "sky_azure",
}

CHROME = {
    "fjord_hammer": {"bar_lift": 4, "selection_alpha": "4A", "focus": "accent"},
    "alpenglow_paper": {"bar_lift": 4, "selection_alpha": "3C", "focus": "muted"},
    "kimbie_warm": {"bar_lift": 3, "selection_alpha": "5A", "focus": "accent2"},
    "forest_canopy": {"bar_lift": 2, "selection_alpha": "56", "focus": "accent2"},
    "lemon_haze": {"bar_lift": 3, "selection_alpha": "40", "focus": "accent"},
    "lemon_custard": {"bar_lift": 2, "selection_alpha": "50", "focus": "accent", "selection": "accent2"},
    "cherry_cream": {"bar_lift": 2, "selection_alpha": "35", "focus": "accent", "selection": "accent2"},
    "sky_azure": {"bar_lift": 2, "selection_alpha": "40", "focus": "accent", "selection": "accent2"},
    "night_siren": {"bar_lift": 0, "selection_alpha": "7A", "focus": "accent2"},
    "high_contrast_signal": {"bar_lift": 0, "selection_alpha": "88", "focus": "accent"},
}


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slim_palette(data: dict, slug: str) -> dict:
    """Canon form: display-aligned slug, role hex, lineage — no essay fields."""
    display = data.get("theme_display_name") or data.get("theme_name") or f"RR {slug_to_display(slug)}"
    if not str(display).startswith("RR "):
        display = f"RR {slug_to_display(slug)}"
    roles = role_map(data)
    colors = []
    bg = roles.get("background", "#111111")
    fg = roles.get("foreground", "#FAFAFA")
    from core.math_engine import contrast_ratio

    for role, hx in roles.items():
        colors.append(
            {
                "role": role,
                "hex": hx,
                "hsl": list(hex_to_hsl(hx)),
                "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
                "contrast_with_background": round(contrast_ratio(hx, bg), 2),
            }
        )
    return {
        "id": data["id"],
        "context": "ide",
        "style_archetype": slug,
        "is_light": bool(data.get("is_light")),
        "theme_display_name": display,
        "theme_name": display,
        "hue_family": data.get("hue_family"),
        "taste_mood": data.get("taste_mood") or ("fjord_ink" if data.get("is_light") else "nocturne_labs"),
        "colors": colors,
        "user_prompt": data.get("user_prompt") or "canon bootstrap",
        "genome_version": "2.0.0",
        "generated": data.get("generated") or _iso(),
        "canon": True,
    }


def _build_genome(slugs: list[str], priors: dict) -> dict:
    dark = priors.get("dark") or {}
    light = priors.get("light") or {}
    return {
        "version": "2.0.0",
        "created": _iso(),
        "last_modified": _iso(),
        "notes": "Slim numeric DNA — bootstrapped from kept canon. Compounding lives in knowledge/priors.json.",
        "contrast_philosophy": {
            "mode": "readability_first",
            "min_contrast_ratio": 4.5,
            "ui_min_contrast_ratio": 4.5,
            "token_min_contrast_ratio": 3.2,
            "dark_bg_preference": True,
        },
        "saturation_profile": {
            "base_saturation": [8, 22],
            "accent_saturation": [
                max(40, (dark.get("accent_sat_mean") or 70) - 12),
                min(95, (dark.get("accent_sat_mean") or 70) + 12),
            ],
        },
        "lightness_profile": {
            "background_range": dark.get("bg_light_range") or [6, 16],
            "foreground_range": [88, 98],
            "midtone_range": [38, 58],
        },
        "hue_strategy": {
            "base_hue_range": [210, 270],
            "accent_hue_center": dark.get("accent_hue_center") or 285,
            "accent_hue_range": [260, 320],
        },
        "style_archetypes": {"ide": slugs},
        "context_overrides": {
            "ide": {
                "token_differentiation_priority": "high",
                "syntax_color_count": 6,
                "tone_controls": {"calmness": 0.55, "vibrancy": 0.7, "separation": 0.75},
            }
        },
        "compounding": {
            "source": "knowledge/priors.json",
            "light_accent_center": light.get("accent_hue_center"),
            "dark_accent_center": dark.get("accent_hue_center"),
            "canon_count": priors.get("canon_count", 0),
        },
    }


def main() -> None:
    palette_dir = ROOT / "outputs" / "palettes"
    roster_path = registry_dir(ROOT) / "theme_roster.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    kept_ids = list(roster.get("palette_ids") or [])
    if not kept_ids:
        raise SystemExit("No kept palettes in roster — abort")

    print(f"Canon ids ({len(kept_ids)}): {kept_ids}")

    # 1) Load + rename slugs to display-aligned
    canon: list[dict] = []
    skus: dict[str, dict] = {}
    for pid in kept_ids:
        path = palette_dir / f"{pid}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        display = data.get("theme_display_name") or data.get("theme_name") or ""
        slug = display_to_slug(display)
        # Prefer display slug; fall back through legacy alias
        legacy = normalize_slug(str(data.get("style_archetype") or ""))
        if slug != legacy and LEGACY_SLUG_ALIASES.get(str(data.get("style_archetype"))) == slug:
            pass
        elif not slug:
            slug = legacy
        slim = _slim_palette(data, slug)
        path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
        canon.append(slim)
        tier = "pro" if slug in PRO_SLUGS else "free" if slug in FREE_SLUGS else "free"
        skus[slug] = {
            "display": slug_to_display(slug),
            "rr_name": slim["theme_display_name"],
            "tier": tier,
            "mode": "curated" if slug in CURATED_SLUGS else "generative",
            "palette_id": pid,
            "is_light": slim["is_light"],
            "chrome": CHROME.get(slug, {"bar_lift": 2, "selection_alpha": "55", "focus": "accent"}),
        }
        print(f"  {pid} -> {slim['theme_display_name']} [{slug}] ({tier}/{skus[slug]['mode']})")

    # 2) Delete orphans (everything not kept)
    removed = []
    for path in sorted(palette_dir.glob("ide_palette_*.json")):
        if path.stem not in kept_ids:
            path.unlink()
            removed.append(path.stem)
    print(f"Nuked orphan drafts: {removed}")

    # 3) Wipe knowledge + rebuild
    kdir = knowledge_dir(ROOT)
    for name in ("ledger.jsonl", "priors.json", "skus.json"):
        p = kdir / name
        if p.exists():
            p.unlink()

    save_skus(ROOT, {"version": 1, "skus": skus, "bootstrapped_at": _iso()})

    # Seed ledger with bootstrap keeps so compounding has history
    for p in canon:
        append_ledger(
            ROOT,
            {
                "type": "keep",
                "palette_id": p["id"],
                "slug": p["style_archetype"],
                "is_light": p["is_light"],
                "accent_hue": hex_to_hsl(role_map(p)["accent_primary"])[0],
                "prompt": "canon bootstrap",
                "roles": role_map(p),
                "bootstrap": True,
            },
        )

    priors = recompute_priors(ROOT, canon)
    print(f"Priors: dark@{priors.get('dark', {}).get('accent_hue_center')} light@{priors.get('light', {}).get('accent_hue_center')}")

    # 4) Replace genome with slim v2
    gpath = genome_path(ROOT)
    hist = ROOT / "genome" / "genome_history"
    hist.mkdir(parents=True, exist_ok=True)
    if gpath.is_file():
        shutil.copy2(gpath, hist / f"genome_v1_pre_reboot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json")
    slugs = [p["style_archetype"] for p in canon]
    genome = _build_genome(slugs, priors)
    gpath.write_text(json.dumps(genome, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote genome v2 with {len(slugs)} archetypes")

    # 5) Reset session (no draft)
    session = {
        "version": 1,
        "draft_palette_id": None,
        "chain": [],
        "last_prompt": None,
        "updated_at": _iso(),
    }
    (registry_dir(ROOT) / "ide_iteration_session.json").write_text(
        json.dumps(session, indent=2) + "\n", encoding="utf-8"
    )

    # 6) Rewrite theme_tiers with canonical slugs (no marketing remaps needed)
    tiers = {
        "product": "Rob Ross IDE Themes",
        "pricing": {
            "model": "one_time",
            "pro_usd": 6.99,
            "currency": "USD",
            "includes": "pro_theme_pack_only",
            "excludes": ["generator", "studio", "genome_sync", "subscription"],
        },
        "channels": {
            "free": ["vscode_marketplace", "openvsx"],
            "pro": ["vscode_marketplace", "gumroad", "itch"],
        },
        "free": FREE_SLUGS,
        "pro": PRO_SLUGS,
        "marketing_names": {},
    }
    (registry_dir(ROOT) / "theme_tiers.json").write_text(json.dumps(tiers, indent=2) + "\n", encoding="utf-8")

    # 7) Clear dead user_loop / shortlist
    roster_clean = {
        "palette_ids": kept_ids,
        "entries": {
            pid: {
                "added_at": (roster.get("entries") or {}).get(pid, {}).get("added_at") or _iso(),
                "prompt": (roster.get("entries") or {}).get(pid, {}).get("prompt") or "canon",
                "slug": next(p["style_archetype"] for p in canon if p["id"] == pid),
            }
            for pid in kept_ids
        },
    }
    roster_path.write_text(json.dumps(roster_clean, indent=2) + "\n", encoding="utf-8")

    # 8) Export + install roster-only
    result = finalize_ide_themes(ROOT)
    print("Export:", result)
    print("REBOOT COMPLETE")


if __name__ == "__main__":
    main()
