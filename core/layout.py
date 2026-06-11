"""Repo layout: genome (taste DNA) vs registry (state) vs sites (consumers)."""

from __future__ import annotations

import shutil
from pathlib import Path

GENOME_FILENAME = "genome_v1.json"
ROSTER_FILENAME = "theme_roster.json"
SESSION_FILENAME = "ide_iteration_session.json"
USER_LOOP_FILENAME = "user_loop_state.json"
CONSUMERS_FILENAME = "consumers.json"

_LEGACY_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("genome/theme_roster.json", f"registry/{ROSTER_FILENAME}"),
    ("genome/ide_iteration_session.json", f"registry/{SESSION_FILENAME}"),
    ("genome/user_loop_state.json", f"registry/{USER_LOOP_FILENAME}"),
    ("genome/web_consumers.json", f"sites/{CONSUMERS_FILENAME}"),
)


def genome_dir(root: Path) -> Path:
    d = root / "genome"
    d.mkdir(parents=True, exist_ok=True)
    return d


def registry_dir(root: Path) -> Path:
    d = root / "registry"
    d.mkdir(parents=True, exist_ok=True)
    _migrate_legacy(root)
    return d


def sites_dir(root: Path) -> Path:
    d = root / "sites"
    d.mkdir(parents=True, exist_ok=True)
    _migrate_legacy(root)
    return d


def genome_path(root: Path) -> Path:
    return genome_dir(root) / GENOME_FILENAME


def consumers_path(root: Path) -> Path:
    return sites_dir(root) / CONSUMERS_FILENAME


def _migrate_legacy(root: Path) -> None:
    for old_rel, new_rel in _LEGACY_MIGRATIONS:
        old = root / old_rel
        new = root / new_rel
        if old.is_file() and not new.is_file():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))
