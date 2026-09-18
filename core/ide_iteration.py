"""Chat iteration loop — draft palettes, keep winners, ship roster + draft."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.compound import invent_fork_slug
from core.ide_schema import enrich_legacy_palette, normalize_style, palette_meta
from core.knowledge import load_priors
from core.layout import SESSION_FILENAME, registry_dir
from core.revise import detect_fork_intent
from core.roster import load_roster, roster_add, roster_remove
from core.sku import slug_to_display

STYLE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("cherry cream", "cherry frosting", "cherry shortcake"), "cherry_cream"),
    (("custard", "chiffon", "lemon custard", "lemon cream"), "lemon_custard"),
    (("lemon haze", "yellow haze", "lemon yellow", "lemon paper"), "lemon_haze"),
    (("violet mist", "lavender mist", "purple mist"), "violet_mist"),
    (("violet nocturne", "purple nocturne"), "violet_nocturne"),
    (("forest", "canopy"), "forest_canopy"),
    (("alpenglow", "editorial"), "alpenglow_paper"),
    (("sky azure", "azure sky", "baby blue", "azure"), "sky_azure"),
    (("fjord", "ice"), "fjord_hammer"),
    (("kimbie",), "kimbie_warm"),
    (("night siren", "siren"), "night_siren"),
    (("high contrast", "signal"), "high_contrast_signal"),
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_style_from_prompt(prompt: str, *, default: str | None = None) -> str | None:
    """Return a known SKU slug if the prompt names one; else None (compound invents)."""
    text = prompt.lower()
    for keywords, style in STYLE_HINTS:
        if any(k in text for k in keywords):
            return style
    return default


def _tweak_controls_from_feedback(prompt: str, variety: float, adherence: float) -> tuple[float, float]:
    text = prompt.lower()
    v, a = variety, adherence
    if any(w in text for w in ("more", "wilder", "brighter", "punchier", "vivid")):
        v = min(1.0, v + 0.12)
    if any(w in text for w in ("subtle", "muted", "softer", "calmer", "less")):
        v = max(0.0, v - 0.12)
    if any(w in text for w in ("closer", "exactly", "match", "lock", "same")):
        a = min(1.0, a + 0.15)
    if any(w in text for w in ("different", "try another", "surprise")):
        v = min(1.0, v + 0.2)
        a = max(0.0, a - 0.1)
    return v, a


def session_path(registry: Path) -> Path:
    return registry / SESSION_FILENAME


def load_iteration_session(registry: Path) -> dict[str, Any]:
    p = session_path(registry)
    if not p.is_file():
        return {"version": 1, "draft_palette_id": None, "chain": [], "last_prompt": None}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("draft_palette_id", None)
    data.setdefault("chain", [])
    data.setdefault("last_prompt", None)
    return data


def save_iteration_session(registry: Path, data: dict[str, Any]) -> None:
    p = session_path(registry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def kept_palette_ids(registry: Path) -> list[str]:
    """Explicitly kept themes only — never auto-seeded."""
    return list(load_roster(registry).get("palette_ids") or [])


def ship_palette_ids(root: Path) -> list[str]:
    """Kept roster + current draft (if draft is not already kept)."""
    reg = registry_dir(root)
    kept = kept_palette_ids(reg)
    session = load_iteration_session(reg)
    draft = session.get("draft_palette_id")
    ids = list(dict.fromkeys(kept + ([draft] if draft and draft not in kept else [])))
    return sorted(ids)


def record_draft(root: Path, palette_id: str, prompt: str, *, derived_from: str | None) -> None:
    reg = registry_dir(root)
    session = load_iteration_session(reg)
    chain = list(session.get("chain") or [])
    if derived_from and derived_from not in chain:
        chain.append(derived_from)
    if palette_id not in chain:
        chain.append(palette_id)
    session["draft_palette_id"] = palette_id
    session["chain"] = chain
    session["last_prompt"] = prompt
    session["updated_at"] = _iso_now()
    save_iteration_session(reg, session)


def load_palette(root: Path, palette_id: str) -> dict[str, Any]:
    path = root / "outputs" / "palettes" / f"{palette_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Palette not found: {path}")
    return enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8")))


def discard_ide_palette(root: Path, palette_id: str) -> dict[str, Any]:
    """Reject an unkept draft — negative taste signal; delete draft JSON.

    Kept/canon themes must use remove_ide_palette() instead.
    """
    from core.canon import UseRemoveError, is_kept_palette, load_canon_palettes
    from core.ide_theme import finalize_ide_themes
    from core.knowledge import record_discard, recompute_priors
    from core.roster import load_roster

    if is_kept_palette(root, palette_id):
        raise UseRemoveError(
            f"{palette_id} is on the kept roster. "
            "Use remove() to retire canon themes; discard() is only for unkept drafts."
        )

    reg = registry_dir(root)
    palette_dir = root / "outputs" / "palettes"
    path = palette_dir / f"{palette_id}.json"
    pal = load_palette(root, palette_id) if path.is_file() else None
    if pal:
        record_discard(root, pal)

    roster_remove(reg, palette_id)
    session = load_iteration_session(reg)
    if session.get("draft_palette_id") == palette_id:
        session["draft_palette_id"] = None
        save_iteration_session(reg, session)
    # GC draft files that are not kept
    kept = set(load_roster(reg).get("palette_ids") or [])
    if palette_id not in kept and path.is_file():
        path.unlink()

    recompute_priors(root, load_canon_palettes(root))

    export = finalize_ide_themes(root)
    return {"palette_id": palette_id, "discarded": True, "export": export}


def keep_ide_palette(root: Path, palette_id: str, *, prompt: str | None = None) -> dict[str, Any]:
    """Human strategic keep — compounds into ledger + priors + SKU registry.

    If this draft revises an existing SKU (same slug, or derived_from a kept
    palette of that slug), the previous palette_id is removed from the roster
    so priors/DNA reflect only the successor. Discarding a draft leaves DNA as-was.
    """
    from core.ide_theme import finalize_ide_themes
    from core.knowledge import record_keep, recompute_priors, role_map
    from core.math_engine import hex_to_hsl
    from core.sku import get_sku, upsert_sku

    palette_dir = root / "outputs" / "palettes"
    reg = registry_dir(root)
    pal = load_palette(root, palette_id)
    slug = str(pal.get("style_archetype") or "")
    replaced_id = _resolve_superseded_palette_id(root, pal, slug)

    if replaced_id and replaced_id != palette_id:
        roster_remove(reg, replaced_id)

    roster_add(reg, palette_dir, palette_id, prompt=prompt or pal.get("user_prompt"))
    session = load_iteration_session(reg)
    session["draft_palette_id"] = palette_id
    save_iteration_session(reg, session)

    record_keep(
        root,
        pal,
        prompt=prompt or pal.get("user_prompt"),
        replaces=replaced_id if replaced_id and replaced_id != palette_id else None,
    )

    existing = get_sku(root, slug) or {}
    roles = role_map(pal)
    upsert_sku(
        root,
        slug,
        display=str(pal.get("theme_display_name") or "").removeprefix("RR ").strip()
        or existing.get("display"),
        rr_name=pal.get("theme_display_name") or existing.get("rr_name"),
        tier=existing.get("tier") or "pro",
        mode=existing.get("mode") or "curated",
        palette_id=palette_id,
        is_light=bool(pal.get("is_light")),
        accent_hue=hex_to_hsl(roles["accent_primary"])[0] if roles.get("accent_primary") else None,
    )

    # Recompound from full roster (old version no longer present)
    from core.roster import load_roster

    canon = []
    for pid in load_roster(reg).get("palette_ids") or []:
        p = palette_dir / f"{pid}.json"
        if p.is_file():
            canon.append(json.loads(p.read_text(encoding="utf-8")))
    priors = recompute_priors(root, canon)

    export = finalize_ide_themes(root)
    return {
        "palette_id": palette_id,
        "theme_name": pal.get("theme_name"),
        "kept": True,
        "replaced": replaced_id if replaced_id and replaced_id != palette_id else None,
        "export": export,
        "installed": bool(export.get("installed")),
        "compounding": {
            "canon_count": priors.get("canon_count"),
            "keep_count": priors.get("keep_count"),
        },
    }


def _resolve_superseded_palette_id(
    root: Path, pal: dict[str, Any], slug: str
) -> str | None:
    """Find the kept palette this keep should replace in DNA/roster."""
    from core.sku import get_sku

    pid = str(pal.get("id") or "")
    sku = get_sku(root, slug) if slug else None
    if sku and sku.get("palette_id") and sku["palette_id"] != pid:
        return str(sku["palette_id"])

    derived = pal.get("derived_from")
    if not derived:
        return None
    reg = registry_dir(root)
    kept = set(kept_palette_ids(reg))
    if derived not in kept:
        # Walk chain: parent may be an unkept draft; find kept ancestor same slug
        cursor: str | None = str(derived)
        seen: set[str] = set()
        while cursor and cursor not in seen:
            seen.add(cursor)
            if cursor in kept:
                try:
                    ancestor = load_palette(root, cursor)
                except FileNotFoundError:
                    break
                if str(ancestor.get("style_archetype") or "") == slug:
                    return cursor
                break
            try:
                node = load_palette(root, cursor)
            except FileNotFoundError:
                break
            cursor = node.get("derived_from")
        return None
    try:
        parent = load_palette(root, str(derived))
    except FileNotFoundError:
        return None
    if str(parent.get("style_archetype") or "") == slug:
        return str(derived)
    return None


def iterate_ide_palette(
    root: Path,
    prompt: str,
    *,
    from_palette_id: str | None = None,
    style: str | None = None,
    name: str | None = None,
    is_light: bool | None = None,
    fork: bool | None = None,
) -> dict[str, Any]:
    """Next attempt in a chat iteration — inherits prior slot, new id, auto ships.

    ``fork=True`` (or detected from prompt) creates a **sibling SKU** from the parent
    without replacing it on keep. Same slug revision remains the default when fork
    is false and the prompt does not ask for a separate theme.
    """
    from core.ide_theme import make_ide_palette

    reg = registry_dir(root)
    session = load_iteration_session(reg)
    parent_id = from_palette_id or session.get("draft_palette_id")
    variety, adherence = 0.55, 0.75
    resolved_style = style if style is not None else infer_style_from_prompt(prompt)
    do_fork = fork if fork is not None else detect_fork_intent(prompt)

    if parent_id:
        parent = load_palette(root, parent_id)
        meta = palette_meta(parent)
        parent_slug = str(parent.get("style_archetype") or meta["style_archetype"])
        if do_fork and style is None:
            priors = load_priors(root)
            known = frozenset(priors.get("slugs") or [])
            resolved_style = invent_fork_slug(
                prompt,
                parent_slug=parent_slug,
                is_light=bool(is_light if is_light is not None else parent.get("is_light", True)),
                known_slugs=known,
            )
        elif style is None and resolved_style is None:
            resolved_style = parent_slug
        elif style is None and resolved_style is not None:
            pass  # prompt named a SKU
        if is_light is None:
            is_light = bool(parent.get("is_light", meta["is_light"]))
        gc = parent.get("generation_controls") or {}
        variety = float(gc.get("chromatic_variety", variety))
        adherence = float(gc.get("prompt_adherence", adherence))
        variety, adherence = _tweak_controls_from_feedback(prompt, variety, adherence)
        iteration_index = int(parent.get("iteration_index", 0)) + 1
    else:
        iteration_index = 1
        do_fork = True if fork is None else fork

    display_name = name
    if do_fork and not name and resolved_style:
        display_name = slug_to_display(resolved_style)

    return make_ide_palette(
        root,
        prompt,
        style=resolved_style,
        is_light=is_light,
        name=display_name,
        variety=variety,
        adherence=adherence,
        derived_from=parent_id,
        iteration_index=iteration_index,
        fork=do_fork,
    )
