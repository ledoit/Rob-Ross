"""Web Color Studio — load, tweak, save website palettes on disk."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.export.css_site_tokens import export_palette_file, palette_to_css
from core.genome import load_genome
from core.harmony import HARMONY_MODES, describe_harmony
from core.math_engine import contrast_ratio, hex_to_hsl
from core.pathways.web import build_web_palette
from core.pathways.web_sites import SITE_PROFILES, get_site_profile, normalize_site_id
from core.preview_web_html import build_web_preview_page, load_web_palettes_from_dir

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex(color: str) -> str | None:
    raw = color.strip()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not _HEX_RE.match(raw):
        return None
    return raw.lower()


def list_web_palette_meta(palette_dir: Path, site: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pal in load_web_palettes_from_dir(palette_dir, site):
        roles = {c["role"]: c["hex"] for c in pal.get("colors", []) if c.get("role") and c.get("hex")}
        gc = pal.get("generation_controls") or {}
        rows.append(
            {
                "id": pal.get("id"),
                "site": pal.get("site"),
                "harmony_mode": pal.get("harmony_mode"),
                "hue_family": pal.get("hue_family"),
                "user_prompt": pal.get("user_prompt"),
                "taste_context": pal.get("taste_context"),
                "harmony_note": describe_harmony(str(pal.get("harmony_mode", "analogous"))),
                "conflicts_flagged": pal.get("conflicts_flagged") or [],
                "roles": roles,
                "swatches": pal.get("harmony_swatches") or [],
                "generated": pal.get("generated"),
            }
        )
    return rows


def load_palette_file(palette_dir: Path, palette_id: str) -> dict[str, Any]:
    path = palette_dir / f"{palette_id.replace('.json', '')}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Palette not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_web_palette_pinned(genome_dir: Path, palette_id: str) -> bool:
    from core.roster import load_roster

    return palette_id in (load_roster(genome_dir).get("palette_ids") or [])


def next_scratch_palette_id(palette_dir: Path, site: str | None) -> str:
    site_key = normalize_site_id(site)
    max_n = 0
    for path in palette_dir.glob(f"web_{site_key}_palette_*.json"):
        m = re.search(r"_(\d+)$", path.stem)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"web_{site_key}_palette_{max_n + 1:02d}"


def snapshot_palette(palette_dir: Path, palette_id: str) -> Path | None:
    """Write a timestamped backup before destructive edits."""
    src = palette_dir / f"{palette_id.replace('.json', '')}.json"
    if not src.is_file():
        return None
    hist = palette_dir / "_history"
    hist.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = hist / f"{palette_id.replace('.json', '')}_{ts}.json"
    shutil.copy2(src, dest)
    return dest


def save_palette_file(palette_dir: Path, palette: dict[str, Any]) -> Path:
    pid = palette.get("id")
    if not pid:
        raise ValueError("Palette missing id")
    path = palette_dir / f"{pid}.json"
    path.write_text(json.dumps(palette, indent=2), encoding="utf-8")
    return path


def editable_roles_for_site(site: str | None) -> list[str]:
    profile = get_site_profile(site)
    if profile.get("brand_lock"):
        return list(profile.get("accent_roles") or ("accent_primary", "accent_secondary"))
    return [
        "background",
        "surface",
        "foreground",
        "muted",
        "border",
        "accent_primary",
        "accent_secondary",
    ]


def _refresh_color_metrics(palette: dict[str, Any]) -> None:
    colors = palette.get("colors") or []
    bg = next((c["hex"] for c in colors if c.get("role") == "background"), "#000000")
    fg = next((c["hex"] for c in colors if c.get("role") == "foreground"), "#ffffff")
    for c in colors:
        hx = c.get("hex", "")
        if hx.startswith("#") and len(hx) == 7:
            c["hsl"] = list(hex_to_hsl(hx))
            c["contrast_with_foreground"] = round(contrast_ratio(fg, hx), 2)
            c["contrast_with_background"] = round(contrast_ratio(hx, bg), 2)
        else:
            c["hsl"] = None
            c["contrast_with_foreground"] = None
            c["contrast_with_background"] = None
    palette["conflicts_flagged"] = [
        f"{c['role']}_low_contrast_vs_background"
        for c in colors
        if c.get("role") in ("foreground", "muted", "accent_primary")
        and c.get("contrast_with_background") is not None
        and c["contrast_with_background"] < 3.0
    ]


def set_role_hex(
    palette_dir: Path,
    palette_id: str,
    role: str,
    hex_color: str,
    *,
    genome_dir: Path | None = None,
) -> dict[str, Any]:
    hx = normalize_hex(hex_color)
    if not hx:
        raise ValueError("Invalid hex color")
    if genome_dir and is_web_palette_pinned(genome_dir, palette_id):
        snapshot_palette(palette_dir, palette_id)
    pal = load_palette_file(palette_dir, palette_id)
    allowed = set(editable_roles_for_site(pal.get("site")))
    if role not in allowed:
        raise ValueError(f"Role {role!r} is locked for site {pal.get('site')}")
    found = False
    for c in pal.get("colors", []):
        if c.get("role") == role:
            c["hex"] = hx
            c["rationale"] = f"{role} manually edited in Web Studio."
            found = True
            break
    if not found:
        pal.setdefault("colors", []).append(
            {"role": role, "hex": hx, "rationale": "Added in Web Studio."}
        )
    _refresh_color_metrics(pal)
    save_palette_file(palette_dir, pal)
    return pal


def tweak_palette(
    palette_dir: Path,
    genome_path: Path,
    palette_id: str,
    *,
    action: str,
    harmony: str | None = None,
    hue_delta: float | None = None,
    variant_bump: int = 1,
    genome_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Reroll / nudge / re-harmonize.

    Pinned (roster) palettes are never overwritten — a new scratch id is written instead.
    """
    old = load_palette_file(palette_dir, palette_id)
    gdir = genome_dir or genome_path.parent
    pinned = is_web_palette_pinned(gdir, palette_id)
    target_id = palette_id
    bred_new = False
    if pinned:
        snapshot_palette(palette_dir, palette_id)
        target_id = next_scratch_palette_id(palette_dir, old.get("site"))
        bred_new = True

    genome = load_genome(genome_path)
    ps = dict(genome.get("prompt_session") or {})
    if old.get("user_prompt"):
        ps["source_text"] = old["user_prompt"]
    gc_old = old.get("generation_controls") or {}
    if gc_old.get("chromatic_variety") is not None:
        ps["chromatic_variety"] = gc_old["chromatic_variety"]
    if gc_old.get("prompt_adherence") is not None:
        ps["prompt_adherence"] = gc_old["prompt_adherence"]

    base_hue = float(ps.get("accent_hue_center", 210))
    if hue_delta is not None:
        ps["accent_hue_center"] = (base_hue + hue_delta) % 360

    mode = harmony or old.get("harmony_mode") or gc_old.get("harmony_mode") or "analogous"
    if mode not in HARMONY_MODES:
        mode = "analogous"

    import random

    bump = variant_bump
    if action == "reroll":
        bump = random.randint(1, 11)

    m = re.search(r"_(\d+)$", palette_id)
    variant_index = (int(m.group(1)) - 1 if m else 0) + bump

    genome["prompt_session"] = ps
    pal = build_web_palette(
        genome,
        variant_index=variant_index,
        site=old.get("site"),
        harmony_mode=mode,
        user_prompt=old.get("user_prompt"),
        palette_id=target_id,
    )
    if bred_new:
        pal["bred_from"] = palette_id
    save_palette_file(palette_dir, pal)
    pal["_studio_meta"] = {"bred_new": bred_new, "source_id": palette_id if bred_new else None}
    return pal


def palette_to_generate_params(palette: dict[str, Any]) -> dict[str, Any]:
    """Extract UI + genome seed fields from a saved palette JSON."""
    gc = palette.get("generation_controls") or {}
    accent_hue: float | None = None
    for role in ("accent_secondary", "accent_primary"):
        for c in palette.get("colors", []):
            if c.get("role") == role and str(c.get("hex", "")).startswith("#"):
                accent_hue = float(hex_to_hsl(c["hex"])[0])
                break
        if accent_hue is not None:
            break

    harmony = str(palette.get("harmony_mode") or gc.get("harmony_mode") or "")
    return {
        "palette_id": palette.get("id"),
        "prompt": palette.get("user_prompt") or "",
        "site": palette.get("site") or "generic",
        "harmony": harmony if harmony in HARMONY_MODES else "",
        "variety": gc.get("chromatic_variety"),
        "adherence": gc.get("prompt_adherence"),
        "accent_hue_center": accent_hue,
        "hue_family": palette.get("hue_family"),
        "roles": {
            c["role"]: c["hex"]
            for c in palette.get("colors", [])
            if c.get("role") and c.get("hex")
        },
        "swatches": palette.get("harmony_swatches") or [],
    }


def apply_palette_seed_to_genome(genome: dict[str, Any], palette: dict[str, Any]) -> dict[str, Any]:
    """Merge saved palette parameters into prompt_session (breeder for next batch)."""
    params = palette_to_generate_params(palette)
    ps = genome.setdefault("prompt_session", {})
    if params.get("prompt"):
        ps["source_text"] = params["prompt"]
    if params.get("harmony"):
        ps["harmony_mode"] = params["harmony"]
    if params.get("variety") is not None:
        ps["chromatic_variety"] = float(params["variety"])
    if params.get("adherence") is not None:
        ps["prompt_adherence"] = float(params["adherence"])
    if params.get("accent_hue_center") is not None:
        ps["accent_hue_center"] = float(params["accent_hue_center"])
    ps["seed_palette_id"] = params.get("palette_id")
    ps["web_site"] = params.get("site")
    return params


def _saved_row_from_palette(
    pal: dict[str, Any],
    *,
    pinned: bool,
    roster_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = palette_to_generate_params(pal)
    row["id"] = pal.get("id") or row.get("palette_id")
    row["pinned"] = pinned
    row["harmony_note"] = describe_harmony(row.get("harmony") or "analogous")
    if roster_entry:
        row["saved_at"] = roster_entry.get("added_at")
        row["roster_prompt"] = roster_entry.get("prompt")
    return row


def list_saved_web_palettes(genome_dir: Path, palette_dir: Path) -> list[dict[str, Any]]:
    """
    Saved panel: pinned (roster) first, then other web_* palettes on disk.

    Pinning is explicit (Save / roster add). Files on disk always appear so
    nothing "disappears" if theme_roster.json was never written.
    """
    from core.roster import load_roster

    roster = load_roster(genome_dir)
    pinned_ids = [pid for pid in (roster.get("palette_ids") or []) if str(pid).startswith("web_")]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    for pid in pinned_ids:
        seen.add(pid)
        entry = roster.get("entries", {}).get(pid, {})
        try:
            pal = load_palette_file(palette_dir, pid)
            rows.append(_saved_row_from_palette(pal, pinned=True, roster_entry=entry))
        except FileNotFoundError:
            rows.append(
                {
                    "id": pid,
                    "pinned": True,
                    "missing": True,
                    "roster_prompt": entry.get("prompt"),
                    "saved_at": entry.get("added_at"),
                }
            )

    pinned_set = set(pinned_ids)
    for meta in list_web_palette_meta(palette_dir, site=None):
        pid = str(meta.get("id") or "")
        if not pid.startswith("web_") or pid in seen:
            continue
        try:
            pal = load_palette_file(palette_dir, pid)
            rows.append(_saved_row_from_palette(pal, pinned=pid in pinned_set))
        except FileNotFoundError:
            continue

    rows.sort(key=lambda r: (not r.get("pinned"), str(r.get("id", ""))))
    return rows


def studio_boot_payload(root: Path, site: str | None = None) -> dict[str, Any]:
    palette_dir = root / "outputs" / "palettes"
    gdir = root / "genome"
    saved: list[dict[str, Any]] = []
    roster_ids: list[str] = []
    if gdir.is_dir():
        saved = list_saved_web_palettes(gdir, palette_dir)
        roster_ids = [r["id"] for r in saved if r.get("pinned") and r.get("id")]
    return {
        "sites": [
            {
                "id": k,
                "label": v.get("label"),
                "harmony_default": v.get("harmony_default"),
                "brand_lock": v.get("brand_lock"),
            }
            for k, v in SITE_PROFILES.items()
        ],
        "harmonies": [{"id": m, "note": describe_harmony(m)} for m in HARMONY_MODES],
        "palettes": list_web_palette_meta(palette_dir, site),
        "site_filter": normalize_site_id(site) if site else None,
        "saved_ids": roster_ids,
        "saved": saved,
    }


def rebuild_gallery_preview(root: Path, site: str | None = None) -> Path:
    palettes = load_web_palettes_from_dir(root / "outputs" / "palettes", site)
    out = root / "outputs" / "preview" / "web.html"
    build_web_preview_page(palettes, out, title="Rob Ross — Web Color Studio")
    return out
