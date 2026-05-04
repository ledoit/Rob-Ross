"""Single-user loop state: weighted taste moods, bumps from picks, batch precompute."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

STATE_FILENAME = "user_loop_state.json"
MIN_W = 0.08
MAX_W = 3.5
BUMP_EXPORT = 0.14
BUMP_SHORTLIST = 0.08


def default_state(ide_moods: list[str]) -> dict[str, Any]:
    return {
        "version": 1,
        "use_weighted_taste_moods": True,
        "mood_weights": {str(m): 1.0 for m in ide_moods},
        "archetype_weights": {},
        "events_tail": [],
    }


def state_path(genome_dir: Path) -> Path:
    return genome_dir / STATE_FILENAME


def load_user_loop_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_user_loop_state(path: Path, genome: dict[str, Any]) -> dict[str, Any]:
    """Load or create user loop state next to genome."""
    moods = list(genome.get("taste_contexts", {}).get("ide", []) or [])
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("version", 1)
        data.setdefault("use_weighted_taste_moods", True)
        mw = data.setdefault("mood_weights", {})
        for m in moods:
            mw.setdefault(str(m), 1.0)
        data.setdefault("archetype_weights", {})
        data.setdefault("events_tail", [])
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
    data = default_state(moods)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def save_user_loop_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pick_weighted_ide_moods(moods: list[str], weights: dict[str, Any], k: int, rng: random.Random) -> list[str]:
    """Pick k taste moods; weighted without replacement until pool empties, then refill (allows repeats)."""
    if not moods or k <= 0:
        return []
    pool = list(moods)
    out: list[str] = []
    while len(out) < k:
        if not pool:
            pool = list(moods)
        w = [max(MIN_W, float(weights.get(str(m), 1.0))) for m in pool]
        choice = rng.choices(pool, weights=w, k=1)[0]
        out.append(choice)
        pool.remove(choice)
    return out


def precompute_ide_taste_moods(genome: dict[str, Any], ide_count: int, rng: random.Random) -> list[str] | None:
    """Return per-slot taste mood strings, or None to use legacy round-robin in _build_palette_colors."""
    uls = genome.get("user_loop_state")
    if not uls or not uls.get("use_weighted_taste_moods", True):
        return None
    moods = list(genome.get("taste_contexts", {}).get("ide", []) or [])
    if not moods:
        return None
    mw = uls.get("mood_weights") or {}
    return pick_weighted_ide_moods(moods, mw, ide_count, rng)


def _parse_taste_mood_from_palette(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    tc = str(payload.get("taste_context", ""))
    parts = tc.split(":")
    mood = parts[0].strip() if parts else None
    arch = parts[1].strip() if len(parts) > 1 else None
    return (mood or None, arch or None)


def bump_weights_from_palette_json(
    state_path: Path,
    palette_path: Path,
    *,
    export_pick: bool,
) -> dict[str, Any] | None:
    """Raise mood/archetype weights from a saved palette. Returns small stats dict or None."""
    if not palette_path.is_file() or not state_path.is_file():
        return None
    payload = json.loads(palette_path.read_text(encoding="utf-8"))
    mood, arch = _parse_taste_mood_from_palette(payload)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    mw = data.setdefault("mood_weights", {})
    aw = data.setdefault("archetype_weights", {})
    delta = BUMP_EXPORT if export_pick else BUMP_SHORTLIST
    stats: dict[str, Any] = {"delta": delta}
    if mood and mood in mw:
        mw[mood] = min(MAX_W, float(mw[mood]) + delta)
        stats["mood"] = mood
    elif mood:
        mw[mood] = 1.0 + delta
        stats["mood"] = mood
    if arch:
        aw.setdefault(arch, 1.0)
        aw[arch] = min(MAX_W, float(aw[arch]) + delta * 0.85)
        stats["archetype"] = arch
    tail = data.setdefault("events_tail", [])
    tail.append(
        {
            "palette_id": payload.get("id", palette_path.stem),
            "export_pick": export_pick,
            "mood": mood,
            "archetype": arch,
        }
    )
    data["events_tail"] = tail[-200:]
    save_user_loop_state(state_path, data)
    return stats


def delete_ide_palette_outputs(palette_dir: Path) -> int:
    """Remove ide_palette_*.json for a clean quick batch."""
    n = 0
    for p in palette_dir.glob("ide_palette_*.json"):
        p.unlink()
        n += 1
    return n
