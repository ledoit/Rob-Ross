"""Append one IDE palette JSON without deleting existing ide_palette_*.json files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.generate import _build_palette_colors, _llm_palette_rationale
from core.genome import load_genome, merge_genomes
from core.lemon_drop_palette import build_lemon_custard_colors
from core.prompt_brief import genome_patch_from_prompt


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_ide_palette_id(palette_dir: Path) -> str:
    nums: list[int] = []
    for p in palette_dir.glob("ide_palette_*.json"):
        try:
            nums.append(int(p.stem.rsplit("_", 1)[-1]))
        except ValueError:
            continue
    return f"ide_palette_{max(nums, default=0) + 1:02d}"


def append_ide_palette(
    root: Path,
    prompt: str,
    *,
    archetype: str,
    variety: float,
    adherence: float,
    palette_id: str | None = None,
    theme_display_name: str | None = None,
) -> Path:
    gpath = root / "genome" / "genome_v1.json"
    palette_dir = root / "outputs" / "palettes"
    palette_dir.mkdir(parents=True, exist_ok=True)

    base = load_genome(gpath)
    merged, _ = merge_genomes(base, genome_patch_from_prompt(prompt))
    ps = merged.setdefault("prompt_session", {})
    ps["chromatic_variety"] = max(0.0, min(1.0, variety))
    ps["prompt_adherence"] = max(0.0, min(1.0, adherence))
    merged.setdefault("style_archetypes", {})["ide"] = [archetype]
    if archetype == "lemon_paper":
        merged["saturation_profile"] = {
            "base_saturation": [38, 58],
            "accent_saturation": [82, 94],
        }
        merged["lightness_profile"] = {
            "background_range": [90, 96],
            "foreground_range": [14, 22],
        }

    pid = palette_id or _next_ide_palette_id(palette_dir)
    if archetype in ("lemon_custard", "lemon_cream"):
        colors = build_lemon_custard_colors()
        family_name = "amber"
        taste_context = "studio_neon:lemon_cream:light"
    else:
        colors, family_name, taste_context = _build_palette_colors(merged, context="ide", variant_index=0)
    role_map = {c["role"]: c["hex"] for c in colors}
    ps_meta = merged.get("prompt_session") or {}
    payload = {
        "id": pid,
        "context": "ide",
        "hue_family": family_name,
        "taste_context": taste_context,
        "design_paradigms_applied": merged.get("design_paradigms", []),
        "techniques_applied": merged.get("techniques", []),
        "genome_version": merged.get("version", "1.0.0"),
        "generated": _iso_now(),
        "colors": colors,
        "palette_rationale": _llm_palette_rationale(merged, "ide", role_map),
        "conflicts_flagged": [],
        "feedback_score": None,
        "feedback_dimensions": {},
        "user_prompt": prompt,
        **({"theme_display_name": theme_display_name} if theme_display_name else {}),
        "generation_controls": {
            "chromatic_variety": float(ps_meta.get("chromatic_variety", 0.55)),
            "prompt_adherence": float(ps_meta.get("prompt_adherence", 0.55)),
            "taste_mood_weighted": False,
        },
    }
    out = palette_dir / f"{pid}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one IDE palette without wiping the batch.")
    parser.add_argument("prompt", help='Color brief, e.g. "lemon yellow"')
    parser.add_argument("--archetype", default="lemon_paper", help="IDE style archetype id")
    parser.add_argument("--variety", type=float, default=0.2)
    parser.add_argument("--adherence", type=float, default=0.9)
    parser.add_argument("--id", dest="palette_id", default=None, help="Force palette id stem")
    parser.add_argument("--display-name", dest="theme_display_name", default=None, help="Theme picker label")
    args = parser.parse_args()
    out = append_ide_palette(
        ROOT,
        args.prompt,
        archetype=args.archetype,
        variety=args.variety,
        adherence=args.adherence,
        palette_id=args.palette_id,
        theme_display_name=args.theme_display_name,
    )
    print(out)


if __name__ == "__main__":
    main()
