"""Interactive feedback loop and genome update proposal."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from core.genome import diff_genomes, versioned_update

console = Console()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _palette_files(palette_dir: Path) -> list[Path]:
    return sorted([p for p in palette_dir.glob("*.json") if p.is_file()])


def collect_feedback(palette_dir: str | Path) -> list[dict[str, Any]]:
    pdir = Path(palette_dir)
    files = _palette_files(pdir)
    if not files:
        return []

    feedback_rows: list[dict[str, Any]] = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        console.rule(f"Palette: {payload.get('id', file.stem)} ({payload.get('context', 'unknown')})")
        for color in payload.get("colors", []):
            hx = color.get("hex", "#000000")
            role = color.get("role", "unknown")
            console.print(f"[bold]{role:>16}[/bold] [black on {hx}]  {hx}  [/black on {hx}]")
        score = IntPrompt.ask("Rate palette (1-5)", default=3)
        dimensions = {
            "legibility": IntPrompt.ask("Legibility (1-5)", default=score),
            "vibe_match": IntPrompt.ask("Vibe match (1-5)", default=score),
            "syntax_separation": IntPrompt.ask("Syntax separation (1-5)", default=score),
            "ui_chrome_balance": IntPrompt.ask("UI chrome balance (1-5)", default=score),
            "fatigue_after_30min": IntPrompt.ask("Low fatigue after 30min (1-5)", default=score),
        }
        note = Prompt.ask("Optional note", default="")
        payload["feedback_score"] = score
        payload["feedback_dimensions"] = dimensions
        payload["feedback_note"] = note
        payload["feedback_at"] = _iso_now()
        file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        feedback_rows.append(
            {
                "palette_id": payload.get("id", file.stem),
                "score": score,
                "dimensions": dimensions,
                "note": note,
            }
        )
    return feedback_rows


def infer_genome_adjustments(genome: dict[str, Any], feedback_rows: list[dict[str, Any]]) -> dict[str, Any]:
    updated = deepcopy(genome)
    if not feedback_rows:
        return updated

    avg = sum(int(r["score"]) for r in feedback_rows) / len(feedback_rows)
    sat = updated.setdefault("saturation_profile", {})
    contrast = updated.setdefault("contrast_philosophy", {})

    if avg < 3:
        # Improve clarity and visual energy when results underperform.
        sat_base = sat.get("base_saturation", [10, 25])
        sat["base_saturation"] = [max(0, sat_base[0] - 2), min(100, sat_base[1] + 5)]
        contrast["min_contrast_ratio"] = max(4.5, float(contrast.get("min_contrast_ratio", 4.5)) + 0.5)
    elif avg >= 4:
        sat_acc = sat.get("accent_saturation", [60, 85])
        sat["accent_saturation"] = [max(0, sat_acc[0] - 3), min(100, sat_acc[1] - 1)]

    return versioned_update(genome, updated)


def propose_genome_diff(current: dict[str, Any], proposed: dict[str, Any]) -> list[dict[str, Any]]:
    return diff_genomes(current, proposed)


def maybe_apply_feedback_to_genome(
    genome: dict[str, Any], feedback_rows: list[dict[str, Any]], approve: bool | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    proposed = infer_genome_adjustments(genome, feedback_rows)
    diffs = propose_genome_diff(genome, proposed)
    if not diffs:
        return genome, diffs, False

    if approve is None:
        approve = Confirm.ask("Apply proposed genome update?", default=True)
    return (proposed if approve else genome), diffs, bool(approve)
