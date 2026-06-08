"""Web-only quick generation (no IDE batch)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.genome import load_genome, merge_genomes
from core.pathways.web import generate_web_batch
from core.pathways.web_sites import normalize_site_id
from core.prompt_brief import genome_patch_from_prompt
from core.roster import load_roster
from core.studio_web import apply_palette_seed_to_genome, load_palette_file


def scratch_unsaved_web_palettes(
    palette_dir: Path,
    genome_dir: Path,
    site: str | None,
) -> tuple[list[str], list[str]]:
    """
    Remove scratch palettes for this site before a new generate.

    Roster-pinned IDs are kept (``roster add`` = saved).
    Returns (removed_ids, kept_ids).
    """
    site_key = normalize_site_id(site)
    protected = set(load_roster(genome_dir).get("palette_ids") or [])
    removed: list[str] = []
    kept: list[str] = []
    for path in sorted(palette_dir.glob(f"web_{site_key}_palette_*.json")):
        pid = path.stem
        if pid in protected:
            kept.append(pid)
            continue
        path.unlink(missing_ok=True)
        removed.append(pid)
    return removed, kept


def run_web_quick(
    root: Path,
    prompt: str,
    *,
    count: int = 4,
    site: str | None = None,
    harmony: str | None = None,
    variety: float | None = None,
    adherence: float | None = None,
    seed_from: str | None = None,
) -> dict[str, Any]:
    gpath = root / "genome" / "genome_v1.json"
    if not gpath.exists():
        raise FileNotFoundError(f"Genome not found: {gpath}")

    base = load_genome(gpath)
    merged = dict(base)
    palette_dir = root / "outputs" / "palettes"
    gdir = gpath.parent

    seed_palette_id: str | None = None
    if seed_from:
        seed_pal = load_palette_file(palette_dir, seed_from)
        apply_palette_seed_to_genome(merged, seed_pal)
        seed_palette_id = seed_from
        site = seed_pal.get("site") or site
        if not harmony:
            harmony = seed_pal.get("harmony_mode") or harmony

    patch = genome_patch_from_prompt(prompt)
    merged, _conf = merge_genomes(merged, patch)
    ps = merged.setdefault("prompt_session", {})
    if variety is not None:
        ps["chromatic_variety"] = max(0.0, min(1.0, variety))
    if adherence is not None:
        ps["prompt_adherence"] = max(0.0, min(1.0, adherence))
    if seed_palette_id:
        ps["seed_palette_id"] = seed_palette_id
    ps["web_site"] = normalize_site_id(site)

    effective_harmony = harmony or ps.get("harmony_mode")

    removed, kept = scratch_unsaved_web_palettes(palette_dir, gdir, site)

    palettes = generate_web_batch(
        merged,
        count=count,
        site=site,
        harmony_mode=effective_harmony,
        user_prompt=prompt,
        output_dir=palette_dir,
    )

    report_path = root / "outputs" / "reports" / f"web_quick_{len(palettes)}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Web quick generation", "", f"- Prompt: {prompt}", f"- Site: {site or 'generic'}", ""]
    for p in palettes:
        lines.append(f"## {p['id']}")
        lines.append(p.get("palette_rationale", ""))
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "generated_count": len(palettes),
        "palettes": palettes,
        "report_path": str(report_path),
        "scratch_removed": removed,
        "scratch_kept": kept,
        "seed_from": seed_palette_id,
    }
