"""Agent-facing API — strategic human control + compounding make loop.

Primary verbs (chat agents import these — do not tell users to run CLI):

    from core.agent_api import make, iterate, keep, discard, remove, roster, show, validate, repair, learn, finalize

Compounding rule: every keep() updates the ledger + priors so the next make
gets better. discard() rejects drafts. remove() retires kept canon themes.

NEVER hand-edit registry/, knowledge/, genome/, or theme tier JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.canon import repair_canon, remove_ide_palette, validate_canon
from core.ide_theme import (
    discard_ide_palette,
    finalize_ide_themes,
    iterate_ide_palette,
    keep_ide_palette,
    make_ide_palette,
)
from core.knowledge import load_priors, read_ledger, recompute_priors
from core.layout import registry_dir
from core.roster import load_roster
from core.sku import list_skus, load_skus


def make(root: Path, prompt: str, **kwargs: Any) -> dict[str, Any]:
    return make_ide_palette(root, prompt, **kwargs)


def iterate(root: Path, prompt: str, **kwargs: Any) -> dict[str, Any]:
    return iterate_ide_palette(root, prompt, **kwargs)


def keep(root: Path, palette_id: str, *, prompt: str | None = None) -> dict[str, Any]:
    return keep_ide_palette(root, palette_id, prompt=prompt)


def discard(root: Path, palette_id: str) -> dict[str, Any]:
    """Reject an unkept draft. Raises UseRemoveError if palette is on the kept roster."""
    return discard_ide_palette(root, palette_id)


def remove(root: Path, target: str, *, reason: str | None = None) -> dict[str, Any]:
    """Retire a kept theme by palette id or slug (e.g. ``bubblegum``, ``ide_palette_16``)."""
    return remove_ide_palette(root, target, reason=reason)


def finalize(root: Path) -> dict[str, Any]:
    return finalize_ide_themes(root)


def validate(root: Path) -> list[str]:
    """Return consistency issues. Empty list means canon state is healthy."""
    return validate_canon(root)


def repair(root: Path) -> dict[str, Any]:
    """Rebuild priors, genome, and tiers from the kept roster after corruption or manual edits."""
    return repair_canon(root)


def roster(root: Path) -> dict[str, Any]:
    """Human/agent strategic view of kept SKUs + compounding stats."""
    reg = load_roster(registry_dir(root))
    skus = list_skus(root)
    priors = load_priors(root)
    palette_dir = root / "outputs" / "palettes"
    rows = []
    for pid in reg.get("palette_ids") or []:
        path = palette_dir / f"{pid}.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "id": pid,
                "display": data.get("theme_display_name"),
                "slug": data.get("style_archetype"),
                "is_light": data.get("is_light"),
                "accent": next(
                    (c["hex"] for c in data.get("colors", []) if c.get("role") == "accent_primary"),
                    None,
                ),
            }
        )
    return {
        "kept": rows,
        "skus": skus,
        "priors": {
            "canon_count": priors.get("canon_count"),
            "keep_count": priors.get("keep_count"),
            "discard_count": priors.get("discard_count"),
            "dark_center": (priors.get("dark") or {}).get("accent_hue_center"),
            "light_center": (priors.get("light") or {}).get("accent_hue_center"),
        },
        "sku_file": load_skus(root),
        "health": validate_canon(root),
    }


def show(root: Path, palette_id: str) -> dict[str, Any]:
    path = root / "outputs" / "palettes" / f"{palette_id}.json"
    if not path.is_file():
        raise FileNotFoundError(palette_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    roles = {c["role"]: c["hex"] for c in data.get("colors", []) if c.get("role") and c.get("hex")}
    return {
        "id": palette_id,
        "display": data.get("theme_display_name"),
        "slug": data.get("style_archetype"),
        "is_light": data.get("is_light"),
        "prompt": data.get("user_prompt"),
        "roles": roles,
        "derived_from": data.get("derived_from"),
        "iteration_index": data.get("iteration_index"),
    }


def learn(root: Path) -> dict[str, Any]:
    """Recompute priors from current roster (lightweight; prefer repair() for full sync)."""
    reg = load_roster(registry_dir(root))
    palette_dir = root / "outputs" / "palettes"
    canon = []
    for pid in reg.get("palette_ids") or []:
        path = palette_dir / f"{pid}.json"
        if path.is_file():
            canon.append(json.loads(path.read_text(encoding="utf-8")))
    priors = recompute_priors(root, canon)
    return {
        "canon_count": priors.get("canon_count"),
        "keep_count": priors.get("keep_count"),
        "discard_count": priors.get("discard_count"),
        "slugs": priors.get("slugs"),
        "ledger_tail": read_ledger(root, limit=5),
        "health": validate_canon(root),
    }


def ledger(root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    return read_ledger(root, limit=limit)
