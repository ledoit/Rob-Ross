"""Genome lifecycle utilities: load/save/version/diff/merge."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_genome() -> dict[str, Any]:
    now = iso_now()
    return {
        "version": "1.1.0",
        "created": now,
        "last_modified": now,
        "sources_ingested": [],
        "hue_strategy": {
            "base_hue_range": [210, 270],
            "accent_hue_range": [280, 320],
            "interval_method": "golden_ratio",
            "notes": "Initial default strategy.",
        },
        "contrast_philosophy": {
            "mode": "readability_first",
            "min_contrast_ratio": 4.5,
            "ui_min_contrast_ratio": 4.5,
            "token_min_contrast_ratio": 3.2,
            "dark_bg_preference": True,
            "notes": "Bias toward readability and dark themes.",
        },
        "saturation_profile": {
            "base_saturation": [10, 25],
            "accent_saturation": [60, 85],
            "notes": "Muted base with vibrant accents.",
        },
        "lightness_profile": {
            "background_range": [8, 18],
            "foreground_range": [85, 97],
            "midtone_range": [40, 60],
            "notes": "Dark UI baseline with bright foreground text.",
        },
        "emotional_register": {
            "primary": "focused",
            "secondary": "nocturnal",
            "tertiary": "slightly_playful",
            "notes": "Starter emotion profile.",
        },
        "palette_math": {
            "methods": ["golden_ratio_hsl", "analogous_split", "triadic_weighted"],
            "notes": "Use deterministic palette math combinations.",
        },
        "design_paradigms": [
            "readability_first",
            "semantic_separation",
            "low_fatigue_long_sessions",
            "accent_as_wayfinding",
            "cohesive_chrome_minimalism",
        ],
        "techniques": [
            "split_complementary_syntax_distribution",
            "simultaneous_contrast_balancing",
            "chroma_taper_for_depth",
            "luminance_ladder_spacing",
            "contextual_accent_reuse",
        ],
        "taste_contexts": {
            "ide": ["nocturne_labs", "fjord_ink", "retro_terminal", "studio_neon", "forest_console"],
            "web": ["editorial_minimal", "product_bold", "calm_enterprise"],
        },
        "style_archetypes": {
            "ide": [
                "dracula_punch",
                "fjord_hammer",
                "alpenglow_paper",
                "kimbie_warm",
                "ion_storm",
                "forest_canopy",
                "void_forge",
                "bonfire_gold",
                "candy_voltage",
                "night_siren",
                "high_contrast_signal",
            ]
        },
        "reference_themes": [
            "dracula",
            "red",
            "solarized_dark",
            "tomorrow_night_blue",
            "cursor_light",
            "kimbie_dark",
            "abyss",
        ],
        "conflict_resolutions": [],
        "context_overrides": {
            "ide": {
                "token_differentiation_priority": "high",
                "max_hues_in_syntax": 8,
                "min_token_distance": 14.0,
                "tone_controls": {
                    "calmness": 0.7,
                    "vibrancy": 0.6,
                    "separation": 0.7,
                    "comment_quietness": 0.75,
                },
                "notes": "IDE requires token legibility differentiation.",
            },
            "web": {
                "brand_flexibility": "high",
                "primary_accent_dominance": True,
                "notes": "Web can lean harder into brand accent.",
            },
        },
        "feedback_schema": {
            "dimensions": [
                "legibility",
                "vibe_match",
                "syntax_separation",
                "ui_chrome_balance",
                "fatigue_after_30min",
            ],
            "scale": "1-5",
            "notes": "Structured scoring used for future adaptive tuning.",
        },
        "genome_weights": {},
    }


def ensure_genome_dir(genome_dir: str | Path) -> Path:
    root = Path(genome_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "genome_history").mkdir(parents=True, exist_ok=True)
    return root


def load_genome(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Genome file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_genome(genome: dict[str, Any], path: str | Path, history_dir: str | Path | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    current = deepcopy(genome)
    current["last_modified"] = iso_now()
    if "created" not in current:
        current["created"] = current["last_modified"]

    with p.open("w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, sort_keys=False)

    if history_dir is not None:
        hist = Path(history_dir)
        hist.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot = hist / f"genome_{current.get('version', 'unknown')}_{ts}.json"
        with snapshot.open("w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, sort_keys=False)
    return p


def _bump_patch(version: str) -> str:
    major, minor, patch = [int(x) for x in version.split(".")]
    return f"{major}.{minor}.{patch + 1}"


def versioned_update(current: dict[str, Any], updates: dict[str, Any], bump: bool = True) -> dict[str, Any]:
    merged = merge_genomes(current, updates)[0]
    if bump:
        merged["version"] = _bump_patch(current.get("version", "1.0.0"))
    merged["last_modified"] = iso_now()
    merged["created"] = current.get("created", merged["last_modified"])
    return merged


def _is_leaf(value: Any) -> bool:
    return not isinstance(value, (dict, list))


def diff_genomes(old: dict[str, Any], new: dict[str, Any], path: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    keys = set(old.keys()) | set(new.keys())
    for key in sorted(keys):
        key_path = f"{path}.{key}" if path else key
        old_v = old.get(key, None)
        new_v = new.get(key, None)
        if isinstance(old_v, dict) and isinstance(new_v, dict):
            diffs.extend(diff_genomes(old_v, new_v, key_path))
            continue
        if old_v != new_v:
            diffs.append({"path": key_path, "old": old_v, "new": new_v})
    return diffs


def merge_genomes(base: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    merged = deepcopy(base)
    conflicts: list[dict[str, Any]] = []

    def _merge(dst: dict[str, Any], src: dict[str, Any], prefix: str = "") -> None:
        for key, src_val in src.items():
            path = f"{prefix}.{key}" if prefix else key
            if key not in dst:
                dst[key] = deepcopy(src_val)
                continue
            dst_val = dst[key]
            if isinstance(dst_val, dict) and isinstance(src_val, dict):
                _merge(dst_val, src_val, path)
            elif dst_val != src_val:
                conflicts.append(
                    {
                        "path": path,
                        "base": dst_val,
                        "incoming": src_val,
                        "resolution": "incoming_overrides",
                    }
                )
                dst[key] = deepcopy(src_val)

    _merge(merged, incoming)
    return merged, conflicts
