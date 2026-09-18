"""SKU registry — single source of truth for slug, display, tier, mode.

Slugs always match the display core (snake_case of the RR picker label without prefix).
Example: RR Lemon Haze → lemon_haze (never lemon_paper).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.layout import knowledge_dir

SKUS_FILENAME = "skus.json"

# Bootstrap map: legacy style_archetype → canonical slug (= display core)
LEGACY_SLUG_ALIASES: dict[str, str] = {
    "lemon_paper": "lemon_haze",
    "lemon_cream": "lemon_custard",
    "lemon_custard": "lemon_custard",
}


def display_to_slug(display: str) -> str:
    """'RR Lemon Haze' / 'Lemon Haze' → lemon_haze."""
    core = display.strip()
    lower = core.lower()
    for prefix in ("rob ross ", "robross ", "rr "):
        if lower.startswith(prefix):
            core = core[len(prefix) :].strip()
            break
    return "_".join(core.lower().split())


def slug_to_display(slug: str) -> str:
    return slug.replace("_", " ").title()


def normalize_slug(slug: str) -> str:
    s = str(slug or "").strip().lower().replace(" ", "_").replace("-", "_")
    return LEGACY_SLUG_ALIASES.get(s, s)


def skus_path(root: Path) -> Path:
    return knowledge_dir(root) / SKUS_FILENAME


def load_skus(root: Path) -> dict[str, Any]:
    path = skus_path(root)
    if not path.is_file():
        return {"version": 1, "skus": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_skus(root: Path, data: dict[str, Any]) -> Path:
    path = skus_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def get_sku(root: Path, slug: str) -> dict[str, Any] | None:
    slug = normalize_slug(slug)
    return load_skus(root).get("skus", {}).get(slug)


def list_skus(root: Path, *, tier: str | None = None) -> list[dict[str, Any]]:
    skus = load_skus(root).get("skus", {})
    out = []
    for slug, meta in skus.items():
        row = {"slug": slug, **meta}
        if tier and row.get("tier") != tier:
            continue
        out.append(row)
    return sorted(out, key=lambda r: (r.get("tier", ""), r["slug"]))


def delete_sku(root: Path, slug: str) -> bool:
    """Remove a SKU from knowledge/skus.json. Returns True if it existed."""
    slug = normalize_slug(slug)
    data = load_skus(root)
    skus = data.get("skus", {})
    if slug not in skus:
        return False
    del skus[slug]
    save_skus(root, data)
    return True


def upsert_sku(root: Path, slug: str, **fields: Any) -> dict[str, Any]:
    slug = normalize_slug(slug)
    data = load_skus(root)
    skus = data.setdefault("skus", {})
    entry = dict(skus.get(slug) or {})
    entry.update(fields)
    entry.setdefault("display", slug_to_display(slug))
    entry.setdefault("tier", "free")
    entry.setdefault("mode", "generative")  # generative | curated
    skus[slug] = entry
    data["version"] = int(data.get("version") or 1)
    save_skus(root, data)
    return {"slug": slug, **entry}
