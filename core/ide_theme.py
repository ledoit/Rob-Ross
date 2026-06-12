"""IDE theme pipeline — generation orchestration and VS Code export."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.generate import (
    ARCHETYPE_PROFILES,
    IDE_STYLE_ARCHETYPES,
    _build_palette_colors,
    _llm_palette_rationale,
)
from core.genome import load_genome, merge_genomes
from core.layout import genome_path, registry_dir
from core.live_genome import apply_live_genome
from core.ide_schema import (
    build_ide_palette_payload,
    enrich_legacy_palette,
    normalize_style,
    parse_taste_context,
    resolve_branded_name,
)
from core.ide_iteration import infer_style_from_prompt, record_draft, ship_palette_ids
from core.lemon_drop_palette import build_lemon_custard_colors
from core.red_velvet_palette import build_red_velvet_rose_colors
from core.prompt_brief import genome_patch_from_prompt

LEMON_CURATED = frozenset({"lemon_custard", "lemon_cream"})
RED_VELVET_CURATED = frozenset({"red_velvet_rose"})

# Re-export schema helpers for convenience
__all__ = [
    "build_ide_palette_payload",
    "enrich_legacy_palette",
    "make_ide_palette",
    "iterate_ide_palette",
    "keep_ide_palette",
    "discard_ide_palette",
    "infer_style_from_prompt",
    "parse_taste_context",
    "resolve_branded_name",
    "resolve_theme_name",
    "finalize_ide_themes",
    "install_vsix",
    "list_style_archetypes",
]


def list_style_archetypes() -> list[str]:
    return list(IDE_STYLE_ARCHETYPES) + [a for a in ARCHETYPE_PROFILES if a not in IDE_STYLE_ARCHETYPES]


def default_is_light(style_id: str) -> bool:
    profile = ARCHETYPE_PROFILES.get(normalize_style(style_id), {})
    return str(profile.get("theme_mode", "dark")) == "light"


def next_ide_palette_id(palette_dir: Path) -> str:
    nums: list[int] = []
    for p in palette_dir.glob("ide_palette_*.json"):
        try:
            nums.append(int(p.stem.rsplit("_", 1)[-1]))
        except ValueError:
            continue
    return f"ide_palette_{max(nums, default=0) + 1:02d}"


def _prepare_genome(
    root: Path,
    prompt: str,
    *,
    style: str | None,
    variety: float,
    adherence: float,
) -> dict[str, Any]:
    base = load_genome(genome_path(root))
    merged, _ = merge_genomes(base, genome_patch_from_prompt(prompt))
    merged = apply_live_genome(merged, root)
    ps = merged.setdefault("prompt_session", {})
    ps["chromatic_variety"] = max(0.0, min(1.0, variety))
    ps["prompt_adherence"] = max(0.0, min(1.0, adherence))
    if style:
        merged.setdefault("style_archetypes", {})["ide"] = [normalize_style(style)]
        if style == "lemon_paper":
            merged["saturation_profile"] = {
                "base_saturation": [38, 58],
                "accent_saturation": [82, 94],
            }
            merged["lightness_profile"] = {
                "background_range": [90, 96],
                "foreground_range": [14, 22],
            }
    return merged


def _generate_colors(
    genome: dict[str, Any],
    *,
    style: str,
    is_light: bool | None,
) -> tuple[list[dict[str, Any]], str, str, str, bool]:
    style = normalize_style(style)
    if style in LEMON_CURATED:
        colors = build_lemon_custard_colors()
        return colors, "amber", "studio_neon", style, True
    if style in RED_VELVET_CURATED:
        colors = build_red_velvet_rose_colors()
        return colors, "red", "nocturne_labs", style, False
    colors, family_name, taste_context = _build_palette_colors(genome, context="ide", variant_index=0)
    parsed = parse_taste_context(taste_context)
    if is_light is not None:
        parsed["is_light"] = is_light
    return colors, family_name, parsed["taste_mood"], parsed["style_archetype"], parsed["is_light"]


def write_ide_palette(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def finalize_ide_themes(root: Path, *, all_palettes: bool = False) -> dict[str, Any]:
    """Export VSIX and install into Cursor — ships roster + current draft by default."""
    export_result = run_theme_export(root, all_palettes=all_palettes)
    if export_result.get("vsix"):
        install_vsix(Path(export_result["vsix"]))
        export_result["installed"] = True
    return export_result


def make_ide_palette(
    root: Path,
    prompt: str,
    *,
    style: str | None = None,
    is_light: bool | None = None,
    name: str | None = None,
    palette_id: str | None = None,
    variety: float = 0.55,
    adherence: float = 0.55,
    export: bool = True,
    add_to_roster: bool = False,
    install: bool = True,
    package_vsix: bool = True,
    derived_from: str | None = None,
    iteration_index: int | None = None,
) -> dict[str, Any]:
    """Create one IDE palette from a color brief + style archetype."""
    palette_dir = root / "outputs" / "palettes"
    resolved_style = normalize_style(style or infer_style_from_prompt(prompt))
    genome = _prepare_genome(root, prompt, style=resolved_style, variety=variety, adherence=adherence)
    pid = palette_id or next_ide_palette_id(palette_dir)
    colors, family_name, taste_mood, style_archetype, resolved_light = _generate_colors(
        genome, style=resolved_style, is_light=is_light
    )
    role_map = {c["role"]: c["hex"] for c in colors}
    payload = build_ide_palette_payload(
        palette_id=pid,
        colors=colors,
        hue_family=family_name,
        taste_mood=taste_mood,
        style_archetype=style_archetype,
        is_light=resolved_light,
        genome=genome,
        user_prompt=prompt,
        palette_rationale=_llm_palette_rationale(genome, "ide", role_map),
        theme_display_name=name,
        derived_from=derived_from,
        iteration_index=iteration_index,
    )
    out = write_ide_palette(palette_dir / f"{pid}.json", payload)
    record_draft(root, pid, prompt, derived_from=derived_from)
    result: dict[str, Any] = {
        "palette_id": pid,
        "path": str(out),
        "theme_name": payload["theme_name"],
        "is_light": payload["is_light"],
        "style_archetype": payload["style_archetype"],
        "derived_from": derived_from,
        "iteration_index": iteration_index,
    }
    if add_to_roster:
        from core.roster import roster_add

        roster_add(registry_dir(root), palette_dir, pid, prompt=prompt)
        result["roster_added"] = True
    if export or install:
        export_result = finalize_ide_themes(root) if install else run_theme_export(
            root, package_vsix=package_vsix
        )
        result["export"] = export_result
        if export_result.get("installed"):
            result["installed"] = True
    return result


def _latest_vsix(vsix_dir: Path) -> Path | None:
    files = list(vsix_dir.glob("robross-ide-palettes-*.vsix"))
    if not files:
        return None

    def _patch(path: Path) -> tuple[int, ...]:
        stem = path.stem.rsplit("-", 1)[-1]
        parts = stem.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return tuple(int(p) for p in parts)
        return (0, 0, 0)

    return max(files, key=_patch)


def run_theme_export(
    root: Path,
    *,
    all_palettes: bool = False,
    package_vsix: bool = True,
) -> dict[str, Any]:
    cmd = [sys.executable, str(root / "scripts" / "export_vscode_themes.py")]
    if all_palettes:
        pass
    else:
        ids = ship_palette_ids(root)
        cmd.extend(["--ids", ",".join(ids)])
    if not package_vsix:
        cmd.append("--no-package-vsix")
    subprocess.run(cmd, check=True, cwd=root)
    vsix_dir = root / "vscode-themes"
    latest = _latest_vsix(vsix_dir)
    return {
        "themes_dir": str(vsix_dir / "themes"),
        "vsix": str(latest) if latest else None,
    }


EXTENSION_ID = "local.robross-ide-palettes"
EXTENSION_FOLDER_PREFIX = "local.robross-ide-palettes-"
LEGACY_EXTENSION_IDS = frozenset({EXTENSION_ID, "local.rob-ross-ide-palettes"})


def _cursor_cmd() -> str:
    cmd = shutil.which("cursor") or shutil.which("cursor.cmd")
    if not cmd:
        raise RuntimeError("cursor CLI not found in PATH")
    return cmd


def _cursor_extensions_dir() -> Path | None:
    for key in ("USERPROFILE", "HOME"):
        base = os.environ.get(key)
        if not base:
            continue
        ext = Path(base) / ".cursor" / "extensions"
        if ext.is_dir():
            return ext
    return None


def _cursor_user_dir() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if appdata:
        user = Path(appdata) / "Cursor" / "User"
        if user.is_dir():
            return user
    for key in ("USERPROFILE", "HOME"):
        base = os.environ.get(key)
        if not base:
            continue
        user = Path(base) / "AppData" / "Roaming" / "Cursor" / "User"
        if user.is_dir():
            return user
    return None


def _global_extension_entry() -> dict[str, Any] | None:
    ext_dir = _cursor_extensions_dir()
    if not ext_dir:
        return None
    registry = ext_dir / "extensions.json"
    if not registry.is_file():
        return None
    for entry in json.loads(registry.read_text(encoding="utf-8")):
        if entry.get("identifier", {}).get("id") == EXTENSION_ID:
            return entry
    return None


def sync_extension_to_cursor_profiles() -> list[str]:
    """Mirror the global VSIX install into Cursor profile extensions.json registries.

    `cursor --install-extension` updates ~/.cursor/extensions/extensions.json but
    leaves profile-scoped registries pointing at deleted folders — themes vanish.
    """
    entry = _global_extension_entry()
    if not entry:
        return []
    user_dir = _cursor_user_dir()
    if not user_dir:
        return []
    profiles_dir = user_dir / "profiles"
    if not profiles_dir.is_dir():
        return []
    updated: list[str] = []
    for profile_registry in profiles_dir.glob("*/extensions.json"):
        data = json.loads(profile_registry.read_text(encoding="utf-8"))
        had_rr = any(
            item.get("identifier", {}).get("id") in LEGACY_EXTENSION_IDS for item in data
        )
        if not had_rr:
            continue
        next_data = [
            item
            for item in data
            if item.get("identifier", {}).get("id") not in LEGACY_EXTENSION_IDS
        ]
        next_data.append(entry)
        profile_registry.write_text(
            json.dumps(next_data, separators=(",", ":")),
            encoding="utf-8",
        )
        updated.append(profile_registry.parent.name)
    return updated


def uninstall_stale_extension_versions(*, keep_version: str | None = None) -> list[str]:
    """Remove stacked local.robross-ide-palettes-* folders (Cursor keeps all VSIX installs)."""
    removed: list[str] = []
    ext_dir = _cursor_extensions_dir()
    if not ext_dir:
        return removed
    for folder in sorted(ext_dir.glob(f"{EXTENSION_FOLDER_PREFIX}*")):
        if not folder.is_dir():
            continue
        if keep_version and folder.name == f"{EXTENSION_FOLDER_PREFIX}{keep_version}":
            continue
        shutil.rmtree(folder, ignore_errors=True)
        removed.append(folder.name)
    return removed


def install_vsix(vsix_path: Path) -> None:
    """Install VSIX, then drop older local.robross-ide-palettes-* folders.

    Never delete extension folders before a successful install — a failed install
    after a pre-wipe leaves Cursor with zero RR themes.
    """
    if not vsix_path.is_file():
        raise FileNotFoundError(vsix_path)
    cursor_cmd = _cursor_cmd()
    version = vsix_path.stem.rsplit("-", 1)[-1] if vsix_path.stem else None
    subprocess.run(
        [cursor_cmd, "--install-extension", str(vsix_path.resolve()), "--force"],
        check=True,
    )
    if not version:
        return
    target = f"{EXTENSION_FOLDER_PREFIX}{version}"
    ext_dir = _cursor_extensions_dir()
    if not ext_dir or not (ext_dir / target).is_dir():
        raise RuntimeError(
            f"VSIX install finished but {target} is missing under {ext_dir or '?'}"
        )
    uninstall_stale_extension_versions(keep_version=version)
    sync_extension_to_cursor_profiles()


def iterate_ide_palette(root: Path, prompt: str, **kwargs: Any) -> dict[str, Any]:
    from core.ide_iteration import iterate_ide_palette as _iterate

    return _iterate(root, prompt, **kwargs)


def keep_ide_palette(root: Path, palette_id: str, *, prompt: str | None = None) -> dict[str, Any]:
    from core.ide_iteration import keep_ide_palette as _keep

    return _keep(root, palette_id, prompt=prompt)


def discard_ide_palette(root: Path, palette_id: str) -> dict[str, Any]:
    from core.ide_iteration import discard_ide_palette as _discard

    return _discard(root, palette_id)
