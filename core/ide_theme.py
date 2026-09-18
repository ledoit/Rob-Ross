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
from core.compound import resolve_generation_plan
from core.knowledge import (
    apply_priors_to_session,
    load_priors,
    record_discard,
    record_iterate,
    record_keep,
    recompute_priors,
    role_map as knowledge_role_map,
)
from core.revise import (
    build_rich_purple_roles,
    colors_from_roles,
    nudge_roles_from_feedback,
    wants_rich_purple_shades,
)
from core.sku import get_sku, normalize_slug, slug_to_display
from core.math_engine import hex_to_hsl, contrast_ratio
from core.prompt_brief import genome_patch_from_prompt

# Legacy curated builders — used only if canon file missing
from core.cherry_cream_palette import build_cherry_cream_colors
from core.sky_azure_palette import build_sky_azure_colors
from core.lemon_drop_palette import build_lemon_custard_colors

LEMON_CUSTARD_CURATED = frozenset({"lemon_custard", "lemon_cream"})
CHERRY_CREAM_CURATED = frozenset({"cherry_cream"})
SKY_AZURE_CURATED = frozenset({"sky_azure"})

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
        if style in ("lemon_haze", "lemon_paper"):
            merged["saturation_profile"] = {
                "base_saturation": [38, 58],
                "accent_saturation": [82, 94],
            }
            merged["lightness_profile"] = {
                "background_range": [90, 96],
                "foreground_range": [14, 22],
            }
    return merged


def _colors_from_role_hex(roles: dict[str, str]) -> list[dict[str, Any]]:
    bg = roles.get("background", "#111111")
    fg = roles.get("foreground", "#FAFAFA")
    order = [
        "background",
        "surface",
        "border",
        "muted",
        "foreground",
        "accent_primary",
        "accent_secondary",
        "syntax_1",
        "syntax_2",
        "syntax_3",
        "syntax_4",
        "syntax_5",
        "syntax_6",
    ]
    out = []
    for role in order:
        hx = roles.get(role)
        if not hx:
            continue
        out.append(
            {
                "role": role,
                "hex": hx,
                "hsl": list(hex_to_hsl(hx)),
                "contrast_with_foreground": round(contrast_ratio(fg, hx), 2),
                "contrast_with_background": round(contrast_ratio(hx, bg), 2),
                "genome_principles_applied": ["canon_role_hex"],
                "rationale": f"{role} from kept canon.",
            }
        )
    return out


def _load_canon_colors(root: Path, slug: str) -> list[dict[str, Any]] | None:
    """Existing SKUs resolve from kept palette JSON (source of truth)."""
    sku = get_sku(root, slug)
    if not sku:
        return None
    pid = sku.get("palette_id")
    if not pid:
        return None
    path = root / "outputs" / "palettes" / f"{pid}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return _colors_from_role_hex(knowledge_role_map(data))


def _generate_colors(
    root: Path,
    genome: dict[str, Any],
    *,
    style: str,
    is_light: bool | None,
    math_style: str | None = None,
) -> tuple[list[dict[str, Any]], str, str, str, bool]:
    style = normalize_style(style)

    # 1) Canon SKU — never re-roll product hex
    canon = _load_canon_colors(root, style)
    if canon:
        sku = get_sku(root, style) or {}
        light = bool(sku.get("is_light")) if is_light is None else bool(is_light)
        family = "canon"
        mood = "fjord_ink" if light else "nocturne_labs"
        return canon, family, mood, style, light

    # 2) Legacy curated builders (fallback before reboot / missing sku file)
    if style in LEMON_CUSTARD_CURATED:
        return build_lemon_custard_colors(), "amber", "studio_neon", "lemon_custard", True
    if style in CHERRY_CREAM_CURATED:
        return build_cherry_cream_colors(), "red", "studio_neon", style, True
    if style in SKY_AZURE_CURATED:
        return build_sky_azure_colors(), "blue", "fjord_ink", style, True

    # 3) Generative — math engine; identity slug stays `style`, math uses mode profile
    engine_style = normalize_style(math_style or style)
    genome.setdefault("style_archetypes", {})["ide"] = [engine_style]
    colors, family_name, taste_context = _build_palette_colors(genome, context="ide", variant_index=0)
    parsed = parse_taste_context(taste_context)
    if is_light is not None:
        parsed["is_light"] = is_light
    return colors, family_name, parsed["taste_mood"], style, parsed["is_light"]


def write_ide_palette(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
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
    fork: bool = False,
) -> dict[str, Any]:
    """Create one IDE palette — compounded from kept canon priors + brief.

    When ``derived_from`` is set (iterate), revise parent hexes from feedback —
    never freeze-reload a kept SKU's canon. Product DNA only changes on keep.

    ``fork=True`` keeps a sibling slug (parent stays on roster when the draft is kept).
    """
    from core.compound import invent_fork_slug
    from core.ide_iteration import load_palette

    palette_dir = root / "outputs" / "palettes"
    priors = load_priors(root)
    parent: dict[str, Any] | None = None
    if derived_from:
        parent = load_palette(root, derived_from)

    plan = resolve_generation_plan(
        prompt, priors, style=style, is_light=is_light, name=name
    )
    if parent is not None:
        meta = parent
        parent_slug = str(parent.get("style_archetype") or plan["slug"])
        if fork and style is None:
            resolved_style = invent_fork_slug(
                prompt,
                parent_slug=parent_slug,
                is_light=bool(
                    is_light
                    if is_light is not None
                    else parent.get("is_light", plan["is_light"])
                ),
                known_slugs=frozenset(priors.get("slugs") or []),
            )
        else:
            resolved_style = normalize_slug(style or parent_slug)
        resolved_light = (
            bool(is_light)
            if is_light is not None
            else bool(parent.get("is_light", plan["is_light"]))
        )
        display_name = name or slug_to_display(resolved_style)
        family_name = str(parent.get("hue_family") or "violet")
        taste_mood = str(parent.get("taste_mood") or "default")
    else:
        resolved_style = normalize_slug(plan["slug"])
        resolved_light = bool(plan["is_light"])
        display_name = name or plan["display"]
        family_name = None  # filled by generator
        taste_mood = None

    genome = _prepare_genome(
        root, prompt, style=resolved_style, variety=variety, adherence=adherence
    )
    genome = apply_priors_to_session(
        genome,
        priors,
        accent_hue=plan["accent_hue"],
        is_light=resolved_light,
        variety=variety,
        adherence=adherence,
    )
    # Force theme mode into lightness profile for generative path
    if resolved_light:
        genome.setdefault("lightness_profile", {})["background_range"] = genome.get(
            "lightness_profile", {}
        ).get("background_range") or [88, 96]
        # nudge archetypes toward light profiles when present
        genome.setdefault("prompt_session", {})["forced_light"] = True
    else:
        genome.setdefault("prompt_session", {})["forced_light"] = False

    pid = palette_id or next_ide_palette_id(palette_dir)
    neighbor_slugs = [n.get("slug") for n in plan.get("neighbors") or [] if n.get("slug")]

    if parent is not None:
        parent_roles = knowledge_role_map(parent)
        if wants_rich_purple_shades(prompt):
            nudged = build_rich_purple_roles(
                is_light=resolved_light,
                prompt=prompt,
                parent_roles=parent_roles,
            )
            principles = [
                "fork_from_parent" if fork else "revised_from_parent",
                "rich_purple_spectrum",
                "twilight_periwinkle_ladder",
                f"parent_{derived_from}",
            ]
        else:
            nudged = nudge_roles_from_feedback(
                parent_roles,
                prompt,
                is_light=resolved_light,
                variety=variety,
            )
            principles = [
                "fork_from_parent" if fork else "revised_from_parent",
                "iterate_feedback",
                f"parent_{derived_from}",
            ]
        colors = colors_from_roles(nudged, principles=principles)
        style_archetype = resolved_style
        light_bit = resolved_light
        mode_label = "Fork" if fork else "Iteration"
        rationale = (
            f"{mode_label} of {derived_from} ({resolved_style}): "
            + (
                "rich multi-shade purple ladder (twilight/periwinkle reference). "
                if wants_rich_purple_shades(prompt)
                else "feedback nudge on parent roles (canon freeze bypassed). "
            )
            + _llm_palette_rationale(genome, "ide", nudged)
        )
    else:
        math_style = None
        if not plan["is_existing_sku"]:
            math_style = "fjord_hammer" if resolved_light else "night_siren"
        colors, family_name, taste_mood, style_archetype, light_bit = _generate_colors(
            root,
            genome,
            style=resolved_style,
            is_light=resolved_light,
            math_style=math_style,
        )
        role_hex = {c["role"]: c["hex"] for c in colors}
        rationale = (
            f"Compounded from {priors.get('canon_count', 0)} kept palettes; "
            f"neighbors={neighbor_slugs}; accent≈{plan['accent_hue']:.0f}°; "
            f"novelty={plan.get('novelty', 0):.2f}. "
            + _llm_palette_rationale(genome, "ide", role_hex)
        )

    role_hex = {c["role"]: c["hex"] for c in colors}
    payload = build_ide_palette_payload(
        palette_id=pid,
        colors=colors,
        hue_family=family_name or "ide",
        taste_mood=taste_mood or "default",
        style_archetype=style_archetype,
        is_light=light_bit,
        genome=genome,
        user_prompt=prompt,
        palette_rationale=rationale,
        theme_display_name=display_name,
        derived_from=derived_from,
        iteration_index=iteration_index,
        neighbors=neighbor_slugs,
    )
    out = write_ide_palette(palette_dir / f"{pid}.json", payload)
    record_draft(root, pid, prompt, derived_from=derived_from)
    if derived_from:
        record_iterate(
            root,
            parent_id=derived_from,
            child_id=pid,
            prompt=prompt,
            accent_hue=plan["accent_hue"],
        )
    result: dict[str, Any] = {
        "palette_id": pid,
        "path": str(out),
        "theme_name": payload["theme_name"],
        "is_light": payload["is_light"],
        "style_archetype": payload["style_archetype"],
        "derived_from": derived_from,
        "iteration_index": iteration_index,
        "fork": fork,
        "compounding": {
            "neighbors": neighbor_slugs,
            "accent_hue": plan["accent_hue"],
            "novelty": plan.get("novelty"),
            "canon_count": priors.get("canon_count"),
        },
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


def remove_ide_palette_api(root: Path, target: str, *, reason: str | None = None) -> dict[str, Any]:
    from core.canon import remove_ide_palette as _remove

    return _remove(root, target, reason=reason)
