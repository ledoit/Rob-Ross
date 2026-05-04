"""Theme roster (curated export list) and incremental learning from picks."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.genome import load_genome, merge_genomes, save_genome
from core.generate import IDE_STYLE_ARCHETYPES

ROSTER_FILENAME = "theme_roster.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def roster_path(genome_dir: Path) -> Path:
    return genome_dir / ROSTER_FILENAME


def load_roster(genome_dir: Path) -> dict[str, Any]:
    p = roster_path(genome_dir)
    if not p.exists():
        return {"palette_ids": [], "entries": {}, "shortlist_ids": [], "shortlist_entries": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("palette_ids", [])
    data.setdefault("entries", {})
    data.setdefault("shortlist_ids", [])
    data.setdefault("shortlist_entries", {})
    return data


def save_roster(genome_dir: Path, data: dict[str, Any]) -> Path:
    p = roster_path(genome_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def normalize_palette_id(raw: str) -> str:
    s = raw.strip()
    if not s.endswith(".json"):
        if re.fullmatch(r"ide_palette_\d+", s):
            return s
        return s
    return Path(s).stem


def roster_add(
    genome_dir: Path,
    palette_dir: Path,
    palette_id: str,
    prompt: str | None = None,
) -> dict[str, Any]:
    pid = normalize_palette_id(palette_id)
    pal_file = palette_dir / f"{pid}.json"
    if not pal_file.exists():
        raise FileNotFoundError(f"No palette file: {pal_file}")

    data = load_roster(genome_dir)
    if pid not in data["palette_ids"]:
        data["palette_ids"].append(pid)
    entry = data["entries"].setdefault(pid, {})
    entry["added_at"] = _iso_now()
    if prompt:
        entry["prompt"] = prompt
    save_roster(genome_dir, data)
    return data


def roster_remove(genome_dir: Path, palette_id: str) -> dict[str, Any]:
    pid = normalize_palette_id(palette_id)
    data = load_roster(genome_dir)
    data["palette_ids"] = [x for x in data["palette_ids"] if x != pid]
    data["entries"].pop(pid, None)
    data["shortlist_ids"] = [x for x in data["shortlist_ids"] if x != pid]
    data["shortlist_entries"].pop(pid, None)
    save_roster(genome_dir, data)
    return data


def shortlist_add(
    genome_dir: Path,
    palette_dir: Path,
    palette_id: str,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Intermediary pick: best-of-batch; biases the next quick() regen (not the VS Code export list)."""
    pid = normalize_palette_id(palette_id)
    pal_file = palette_dir / f"{pid}.json"
    if not pal_file.exists():
        raise FileNotFoundError(f"No palette file: {pal_file}")

    data = load_roster(genome_dir)
    if pid not in data["shortlist_ids"]:
        data["shortlist_ids"].append(pid)
    entry = data["shortlist_entries"].setdefault(pid, {})
    entry["picked_at"] = _iso_now()
    if prompt:
        entry["prompt"] = prompt
    save_roster(genome_dir, data)
    return data


def shortlist_remove(genome_dir: Path, palette_id: str) -> dict[str, Any]:
    pid = normalize_palette_id(palette_id)
    data = load_roster(genome_dir)
    data["shortlist_ids"] = [x for x in data["shortlist_ids"] if x != pid]
    data["shortlist_entries"].pop(pid, None)
    save_roster(genome_dir, data)
    return data


def shortlist_clear(genome_dir: Path) -> dict[str, Any]:
    data = load_roster(genome_dir)
    data["shortlist_ids"] = []
    data["shortlist_entries"] = {}
    save_roster(genome_dir, data)
    return data


def apply_shortlist_bias_to_session(
    genome: dict[str, Any],
    roster: dict[str, Any],
    palette_dir: Path,
) -> dict[str, Any] | None:
    """Tighten variety / raise adherence from shortlisted palettes; records breeder ids on prompt_session."""
    ids = list(roster.get("shortlist_ids") or [])
    if not ids:
        return None
    ps = genome.setdefault("prompt_session", {})
    varieties: list[float] = []
    adherences: list[float] = []
    for pid in ids:
        pal = palette_dir / f"{normalize_palette_id(pid)}.json"
        if not pal.is_file():
            continue
        payload = json.loads(pal.read_text(encoding="utf-8"))
        gc = payload.get("generation_controls") or {}
        if "chromatic_variety" in gc:
            varieties.append(float(gc["chromatic_variety"]))
        if "prompt_adherence" in gc:
            adherences.append(float(gc["prompt_adherence"]))
    if varieties:
        breeder_avg = sum(varieties) / len(varieties)
        target_v = max(0.05, min(0.5, breeder_avg * 0.9 - 0.05))
        ps["chromatic_variety"] = min(float(ps.get("chromatic_variety", 0.5)), target_v)
    if adherences:
        breeder_avg_a = sum(adherences) / len(adherences)
        target_a = min(1.0, breeder_avg_a * 1.05 + 0.03)
        ps["prompt_adherence"] = max(float(ps.get("prompt_adherence", 0.5)), target_a)
    ps["shortlist_breeder_ids"] = list(ids)
    return {"shortlist_biased": True, "ids": ids}


def _archetype_from_palette(payload: dict[str, Any]) -> str | None:
    tc = str(payload.get("taste_context", ""))
    parts = tc.split(":")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return None


def learn_from_roster(
    genome: dict[str, Any],
    roster: dict[str, Any],
    palette_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (merged_genome, stats) from rostered IDE palettes."""
    archetype_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    prompts: list[str] = []

    for pid in roster.get("palette_ids", []):
        pal_file = palette_dir / f"{pid}.json"
        if not pal_file.exists():
            continue
        payload = json.loads(pal_file.read_text(encoding="utf-8"))
        arch = _archetype_from_palette(payload)
        if arch:
            archetype_counts[arch] += 1
        fam = str(payload.get("hue_family", ""))
        if fam:
            family_counts[fam] += 1
        up = payload.get("user_prompt") or roster.get("entries", {}).get(pid, {}).get("prompt")
        if isinstance(up, str) and up.strip():
            prompts.append(up.strip())

    if not archetype_counts:
        return genome, {"updated": False, "reason": "no rostered palettes on disk"}

    # Order archetypes: most-liked first, then fill from default IDE list for diversity
    ranked = [a for a, _ in archetype_counts.most_common()]
    tail = [a for a in IDE_STYLE_ARCHETYPES if a not in ranked]
    new_ide_order = ranked + tail

    learned = dict(genome.get("learned_preferences") or {})
    learned["archetype_pick_counts"] = dict(archetype_counts)
    learned["hue_family_pick_counts"] = dict(family_counts)
    learned["last_learned_at"] = _iso_now()
    learned["recent_prompts"] = list(dict.fromkeys(prompts))[:24]

    updates = {
        "style_archetypes": {"ide": new_ide_order},
        "learned_preferences": learned,
    }
    merged, conflicts = merge_genomes(genome, updates)
    stats = {
        "updated": True,
        "archetype_order_top": new_ide_order[:5],
        "conflicts": len(conflicts),
        "palettes_used": sum(archetype_counts.values()),
    }
    return merged, stats


def apply_roster_learning_to_disk(
    genome_path: Path,
    history_dir: Path,
    roster: dict[str, Any],
    palette_dir: Path,
) -> dict[str, Any]:
    genome = load_genome(genome_path)
    merged, stats = learn_from_roster(genome, roster, palette_dir)
    if stats.get("updated"):
        save_genome(merged, genome_path, history_dir)
    return stats
