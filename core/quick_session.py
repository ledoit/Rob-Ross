"""Shared quick-generation pipeline for CLI and Studio UI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.generate import generate_palettes
from core.genome import load_genome, merge_genomes
from core.prompt_brief import apply_prompt_archetype_order, genome_patch_from_prompt
from core.roster import (
    apply_shortlist_bias_to_session,
    load_roster,
    shortlist_add,
    shortlist_clear,
)
from core.user_loop import delete_ide_palette_outputs, ensure_user_loop_state, state_path as user_loop_state_path


def _write_quick_report(root: Path, prompt: str, count: int, result: dict[str, Any]) -> Path:
    report_path = root / "outputs" / "reports" / f"quick_{result['generated_count']}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Quick generation",
        "",
        f"- Prompt: {prompt}",
        f"- Variants: {count}",
        f"- Task plan: `{result['task_plan']}`",
        "",
    ]
    for p in result["palettes"]:
        lines.append(f"## {p['id']}")
        lines.append(p.get("palette_rationale", ""))
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_quick(
    root: Path,
    prompt: str,
    *,
    count: int = 4,
    variety: float | None = None,
    adherence: float | None = None,
    export_themes: bool = False,
    fresh: bool = False,
    shortlist_palette_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Session-only IDE batch from a natural-language brief.

    shortlist_palette_ids: if provided (including empty list), replace shortlist:
      - [] clears shortlist (no breeder bias)
      - non-empty clears then adds each id (must exist on disk before bias step;
        for regen flow, these are *previous* batch ids you liked)
    If shortlist_palette_ids is None, roster shortlist is left unchanged.
    """
    gpath = root / "genome" / "genome_v1.json"
    gdir = gpath.parent
    if not gpath.exists():
        raise FileNotFoundError(f"Genome not found: {gpath}")

    base = load_genome(gpath)
    ensure_user_loop_state(user_loop_state_path(gdir), base)
    palette_dir = root / "outputs" / "palettes"

    if shortlist_palette_ids is not None:
        shortlist_clear(gdir)
        for pid in shortlist_palette_ids:
            shortlist_add(gdir, palette_dir, pid, prompt=prompt or None)

    patch = genome_patch_from_prompt(prompt)
    merged, _conf = merge_genomes(base, patch)
    merged["user_loop_state"] = ensure_user_loop_state(user_loop_state_path(gdir), base)
    ps = merged.setdefault("prompt_session", {})
    if variety is not None:
        ps["chromatic_variety"] = max(0.0, min(1.0, variety))
    if adherence is not None:
        ps["prompt_adherence"] = max(0.0, min(1.0, adherence))
    apply_prompt_archetype_order(merged)
    # Read shortlisted JSON from disk before --fresh removes them.
    shortlist_bias = apply_shortlist_bias_to_session(merged, load_roster(root / "genome"), palette_dir)
    fresh_removed = 0
    if fresh:
        fresh_removed = delete_ide_palette_outputs(palette_dir)

    task = f"make {count} ide palettes"
    result = generate_palettes(task, merged, palette_dir, user_prompt=prompt)
    report_path = _write_quick_report(root, prompt, count, result)

    if export_themes:
        subprocess.run([sys.executable, str(root / "scripts" / "export_vscode_themes.py")], check=True, cwd=root)

    return {
        "generated_count": result["generated_count"],
        "task_plan": result["task_plan"],
        "palettes": result["palettes"],
        "report_path": str(report_path),
        "palette_dir": str(palette_dir),
        "shortlist_bias": shortlist_bias,
        "fresh_removed": fresh_removed,
    }


def list_ide_palette_meta(palette_dir: Path) -> list[dict[str, Any]]:
    """Lightweight rows for Studio checkboxes (no full color arrays)."""
    rows: list[dict[str, Any]] = []
    for p in sorted(palette_dir.glob("ide_palette_*.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        pid = str(payload.get("id", p.stem))
        gc = payload.get("generation_controls") or {}
        rows.append(
            {
                "id": pid,
                "user_prompt": payload.get("user_prompt"),
                "taste_context": payload.get("taste_context"),
                "chromatic_variety": gc.get("chromatic_variety"),
                "prompt_adherence": gc.get("prompt_adherence"),
                "taste_mood_weighted": gc.get("taste_mood_weighted"),
            }
        )
    return rows
