"""Canon lifecycle — the only supported path for retiring or repairing kept themes.

Agents must use remove() / repair() / validate(). Never hand-edit roster, knowledge,
genome, or tier JSON. discard() is for draft rejection only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.genome import load_genome, save_genome
from core.ide_schema import enrich_legacy_palette
from core.knowledge import load_priors, recompute_priors, role_map
from core.layout import genome_dir, genome_path, registry_dir
from core.math_engine import hex_to_hsl
from core.roster import load_roster, roster_remove
from core.sku import delete_sku, get_sku, load_skus, normalize_slug

THEME_TIERS_FILENAME = "theme_tiers.json"


class CanonError(ValueError):
    """Raised when an agent attempts an invalid canon operation."""


class UseRemoveError(CanonError):
    """discard() was called on a kept theme — use remove() instead."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def theme_tiers_path(root: Path) -> Path:
    return registry_dir(root) / THEME_TIERS_FILENAME


def load_theme_tiers(root: Path) -> dict[str, Any]:
    path = theme_tiers_path(root)
    if not path.is_file():
        return {"free": [], "pro": [], "marketing_names": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_theme_tiers(root: Path, data: dict[str, Any]) -> None:
    path = theme_tiers_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_canon_palettes(root: Path) -> list[dict[str, Any]]:
    """Load palette JSON for every id on the kept roster."""
    reg = load_roster(registry_dir(root))
    palette_dir = root / "outputs" / "palettes"
    out: list[dict[str, Any]] = []
    for pid in reg.get("palette_ids") or []:
        path = palette_dir / f"{pid}.json"
        if path.is_file():
            out.append(enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8"))))
    return out


def resolve_palette_target(root: Path, target: str) -> tuple[str, str]:
    """Resolve palette_id or slug → (palette_id, slug)."""
    raw = str(target or "").strip()
    if not raw:
        raise CanonError("remove target is required (palette id or slug)")

    if raw.startswith("ide_palette_"):
        path = root / "outputs" / "palettes" / f"{raw}.json"
        if not path.is_file():
            raise CanonError(f"Palette not found: {raw}")
        pal = enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8")))
        slug = str(pal.get("style_archetype") or "")
        if not slug:
            raise CanonError(f"Palette {raw} has no style_archetype slug")
        return raw, slug

    slug = normalize_slug(raw)
    sku = get_sku(root, slug)
    if sku and sku.get("palette_id"):
        return str(sku["palette_id"]), slug

    reg = load_roster(registry_dir(root))
    palette_dir = root / "outputs" / "palettes"
    for pid in reg.get("palette_ids") or []:
        path = palette_dir / f"{pid}.json"
        if not path.is_file():
            continue
        pal = enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8")))
        if normalize_slug(str(pal.get("style_archetype") or "")) == slug:
            return pid, slug

    raise CanonError(f"No kept palette found for slug or id: {target!r}")


def is_kept_palette(root: Path, palette_id: str) -> bool:
    reg = load_roster(registry_dir(root))
    return palette_id in (reg.get("palette_ids") or [])


def record_remove(
    root: Path,
    palette: dict[str, Any],
    *,
    reason: str | None = None,
) -> None:
    from core.knowledge import append_ledger, palette_signature

    sig = palette_signature(palette)
    append_ledger(
        root,
        {
            "type": "remove",
            "palette_id": sig["palette_id"],
            "slug": sig["slug"],
            "is_light": sig["is_light"],
            "accent_hue": sig["accent_hue"],
            "reason": reason,
            "roles": sig["roles"],
        },
    )


def remove_slug_from_tiers(root: Path, slug: str) -> None:
    slug = normalize_slug(slug)
    tiers = load_theme_tiers(root)
    changed = False
    for key in ("free", "pro"):
        bucket = list(tiers.get(key) or [])
        if slug in bucket:
            tiers[key] = [s for s in bucket if s != slug]
            changed = True
    if changed:
        save_theme_tiers(root, tiers)


def sync_tiers_from_skus(root: Path) -> dict[str, Any]:
    """Rebuild free/pro lists from SKU tier fields."""
    skus = load_skus(root).get("skus", {})
    tiers = load_theme_tiers(root)
    tiers["free"] = sorted(s for s, m in skus.items() if m.get("tier") == "free")
    tiers["pro"] = sorted(s for s, m in skus.items() if m.get("tier") == "pro")
    save_theme_tiers(root, tiers)
    return tiers


def _build_genome_from_canon(slugs: list[str], priors: dict[str, Any]) -> dict[str, Any]:
    dark = priors.get("dark") or {}
    light = priors.get("light") or {}
    return {
        "version": "2.0.0",
        "created": _iso_now(),
        "last_modified": _iso_now(),
        "notes": "Slim numeric DNA — synced from kept canon. Compounding lives in knowledge/priors.json.",
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


def sync_genome_from_canon(root: Path, canon: list[dict[str, Any]], priors: dict[str, Any]) -> dict[str, Any]:
    slugs = [str(p.get("style_archetype") or "") for p in canon if p.get("style_archetype")]
    genome = _build_genome_from_canon(slugs, priors)
    gpath = genome_path(root)
    hist = genome_dir(root) / "genome_history"
    hist.mkdir(parents=True, exist_ok=True)
    if gpath.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        prior = load_genome(gpath)
        (hist / f"genome_v1_pre_sync_{stamp}.json").write_text(
            json.dumps(prior, indent=2) + "\n", encoding="utf-8"
        )
    save_genome(genome, gpath, hist)
    return genome


def clean_user_loop_after_remove(root: Path, *, palette_id: str, slug: str) -> None:
    from core.layout import USER_LOOP_FILENAME
    from core.user_loop import save_user_loop_state

    path = registry_dir(root) / USER_LOOP_FILENAME
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    slug = normalize_slug(slug)
    aw = data.get("archetype_weights") or {}
    if slug in aw:
        aw.pop(slug, None)
        data["archetype_weights"] = aw
    tail = [
        e
        for e in (data.get("events_tail") or [])
        if e.get("palette_id") != palette_id and normalize_slug(str(e.get("archetype") or "")) != slug
    ]
    data["events_tail"] = tail
    save_user_loop_state(path, data)


def clear_draft_if_removed(root: Path, palette_id: str) -> None:
    from core.ide_iteration import load_iteration_session, save_iteration_session

    reg = registry_dir(root)
    session = load_iteration_session(reg)
    if session.get("draft_palette_id") == palette_id:
        session["draft_palette_id"] = None
        save_iteration_session(reg, session)


def remove_ide_palette(
    root: Path,
    target: str,
    *,
    reason: str | None = None,
    export: bool = True,
) -> dict[str, Any]:
    """Retire a kept theme from canon — roster, SKU, tiers, priors, genome, VSIX.

    Accepts ``ide_palette_XX`` or a slug (``bubblegum``, ``choco_raspberry``).
    """
    from core.ide_theme import finalize_ide_themes

    palette_id, slug = resolve_palette_target(root, target)
    if not is_kept_palette(root, palette_id):
        raise CanonError(
            f"{palette_id} ({slug}) is not on the kept roster. "
            "Use discard() for unkept drafts, or repair() if state is inconsistent."
        )

    palette_dir = root / "outputs" / "palettes"
    path = palette_dir / f"{palette_id}.json"
    pal = enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None

    reg = registry_dir(root)
    roster_remove(reg, palette_id)
    delete_sku(root, slug)
    remove_slug_from_tiers(root, slug)
    if pal:
        record_remove(root, pal, reason=reason)
    if path.is_file():
        path.unlink()
    clean_user_loop_after_remove(root, palette_id=palette_id, slug=slug)
    clear_draft_if_removed(root, palette_id)

    canon = load_canon_palettes(root)
    priors = recompute_priors(root, canon)
    sync_genome_from_canon(root, canon, priors)

    export_result: dict[str, Any] | None = None
    if export:
        export_result = finalize_ide_themes(root)

    return {
        "palette_id": palette_id,
        "slug": slug,
        "removed": True,
        "canon_count": priors.get("canon_count"),
        "export": export_result,
        "installed": bool((export_result or {}).get("installed")),
    }


def validate_canon(root: Path) -> list[str]:
    """Return human-readable consistency issues. Empty list = healthy."""
    issues: list[str] = []
    reg = load_roster(registry_dir(root))
    kept_ids = list(reg.get("palette_ids") or [])
    palette_dir = root / "outputs" / "palettes"
    skus = load_skus(root).get("skus", {})
    priors = load_priors(root)
    priors_slugs = set(priors.get("slugs") or [])
    tiers = load_theme_tiers(root)
    tier_slugs = set(tiers.get("free") or []) | set(tiers.get("pro") or [])

    roster_slugs: set[str] = set()
    for pid in kept_ids:
        path = palette_dir / f"{pid}.json"
        if not path.is_file():
            issues.append(f"roster lists {pid} but outputs/palettes/{pid}.json is missing")
            continue
        pal = enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8")))
        slug = normalize_slug(str(pal.get("style_archetype") or ""))
        if slug:
            roster_slugs.add(slug)
        sku = get_sku(root, slug) if slug else None
        if slug and not sku:
            issues.append(f"kept {pid} ({slug}) has no knowledge/skus.json entry")
        elif sku and str(sku.get("palette_id")) != pid:
            issues.append(
                f"SKU {slug} points to {sku.get('palette_id')} but roster keeps {pid}"
            )

    for slug, meta in skus.items():
        pid = meta.get("palette_id")
        if pid and pid not in kept_ids:
            issues.append(f"orphan SKU {slug} references removed palette {pid}")

    if priors_slugs != roster_slugs:
        missing = roster_slugs - priors_slugs
        extra = priors_slugs - roster_slugs
        if missing:
            issues.append(f"priors.json missing slugs: {sorted(missing)}")
        if extra:
            issues.append(f"priors.json has stale slugs: {sorted(extra)}")

    sku_tier_slugs = {s for s, m in skus.items() if m.get("tier") in ("free", "pro")}
    if tier_slugs != sku_tier_slugs:
        issues.append("registry/theme_tiers.json is out of sync with SKU tiers — run repair()")

    gpath = genome_path(root)
    if gpath.is_file():
        genome = load_genome(gpath)
        genome_slugs = set(genome.get("style_archetypes", {}).get("ide") or [])
        if genome_slugs != roster_slugs:
            issues.append("genome style_archetypes.ide does not match roster — run repair()")

    return issues


def repair_canon(root: Path, *, export: bool = True) -> dict[str, Any]:
    """Rebuild priors, genome, and tiers from the kept roster (no ledger wipe)."""
    from core.ide_theme import finalize_ide_themes

    issues_before = validate_canon(root)
    skus = load_skus(root).get("skus", {})
    reg = load_roster(registry_dir(root))
    kept_ids = set(reg.get("palette_ids") or [])

    # Drop orphan SKUs
    for slug in list(skus.keys()):
        pid = skus[slug].get("palette_id")
        if pid and pid not in kept_ids:
            delete_sku(root, slug)

    canon = load_canon_palettes(root)
    priors = recompute_priors(root, canon)
    sync_genome_from_canon(root, canon, priors)
    sync_tiers_from_skus(root)
    issues_after = validate_canon(root)

    export_result: dict[str, Any] | None = None
    if export:
        export_result = finalize_ide_themes(root)

    return {
        "repaired": True,
        "issues_before": issues_before,
        "issues_after": issues_after,
        "canon_count": priors.get("canon_count"),
        "export": export_result,
    }
