"""Append one IDE palette JSON without deleting existing ide_palette_*.json files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ide_theme import make_ide_palette


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one IDE palette without wiping the batch.")
    parser.add_argument("prompt", help='Color brief, e.g. "lemon yellow"')
    parser.add_argument("--style", "--archetype", dest="style", default="lemon_paper", help="IDE style id")
    parser.add_argument("--variety", type=float, default=0.2)
    parser.add_argument("--adherence", type=float, default=0.9)
    parser.add_argument("--id", dest="palette_id", default=None, help="Force palette id stem")
    parser.add_argument("--name", "--display-name", dest="name", default=None, help="Theme label core (RR prefix added)")
    parser.add_argument("--light", action="store_true", help="Force light theme")
    parser.add_argument("--dark", action="store_true", help="Force dark theme")
    parser.add_argument("--export", action="store_true", help="Export VS Code themes after write")
    parser.add_argument("--roster", action="store_true", help="Add palette to export roster")
    args = parser.parse_args()
    if args.light and args.dark:
        raise SystemExit("Use only one of --light or --dark")
    is_light = True if args.light else False if args.dark else None
    result = make_ide_palette(
        ROOT,
        args.prompt,
        style=args.style,
        is_light=is_light,
        name=args.name,
        palette_id=args.palette_id,
        variety=args.variety,
        adherence=args.adherence,
        export=args.export,
        add_to_roster=args.roster,
    )
    print(result["path"])
    print(result["theme_name"], f"({'light' if result['is_light'] else 'dark'})")


if __name__ == "__main__":
    main()
