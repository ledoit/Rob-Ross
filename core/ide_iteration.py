"""Chat iteration loop — draft palettes, keep winners, ship roster + draft."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ide_schema import enrich_legacy_palette, normalize_style, palette_meta
from core.layout import SESSION_FILENAME, registry_dir
from core.roster import load_roster, roster_add, roster_remove

STYLE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("custard", "chiffon", "cream", "lemon cream"), "lemon_cream"),
    (("lemon", "yellow haze", "lemon yellow"), "lemon_paper"),
    (("ocean", "teal", "cyan", "abyss", "deep blue"), "ion_storm"),
    (("forest", "green", "canopy", "earth"), "forest_canopy"),
    (("paper", "editorial", "alpenglow", "calm light"), "alpenglow_paper"),
    (("fjord", "ice", "sky", "baby blue"), "fjord_hammer"),
    (("warm", "kimbie", "amber", "earth"), "kimbie_warm"),
    (("void", "forge", "charcoal"), "void_forge"),
    (("neon", "candy", "voltage", "magenta"), "candy_voltage"),
    (("night", "siren", "crimson"), "night_siren"),
    (("high contrast", "signal", "accessible"), "high_contrast_signal"),
    (("dracula", "purple", "nocturne"), "dracula_punch"),
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_style_from_prompt(prompt: str, *, default: str = "dracula_punch") -> str:
    text = prompt.lower()
    for keywords, style in STYLE_HINTS:
        if any(k in text for k in keywords):
            return style
    if any(w in text for w in ("light", "paper", "bright")):
        return "fjord_hammer"
    if any(w in text for w in ("dark", "black", "night")):
        return "dracula_punch"
    return default


def _tweak_controls_from_feedback(prompt: str, variety: float, adherence: float) -> tuple[float, float]:
    text = prompt.lower()
    v, a = variety, adherence
    if any(w in text for w in ("more", "wilder", "brighter", "punchier", "vivid")):
        v = min(1.0, v + 0.12)
    if any(w in text for w in ("subtle", "muted", "softer", "calmer", "less")):
        v = max(0.0, v - 0.12)
    if any(w in text for w in ("closer", "exactly", "match", "lock", "same")):
        a = min(1.0, a + 0.15)
    if any(w in text for w in ("different", "try another", "surprise")):
        v = min(1.0, v + 0.2)
        a = max(0.0, a - 0.1)
    return v, a


def session_path(registry: Path) -> Path:
    return registry / SESSION_FILENAME


def load_iteration_session(registry: Path) -> dict[str, Any]:
    p = session_path(registry)
    if not p.is_file():
        return {"version": 1, "draft_palette_id": None, "chain": [], "last_prompt": None}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("draft_palette_id", None)
    data.setdefault("chain", [])
    data.setdefault("last_prompt", None)
    return data


def save_iteration_session(registry: Path, data: dict[str, Any]) -> None:
    p = session_path(registry)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def kept_palette_ids(registry: Path) -> list[str]:
    """Explicitly kept themes only — never auto-seeded."""
    return list(load_roster(registry).get("palette_ids") or [])


def ship_palette_ids(root: Path) -> list[str]:
    """Kept roster + current draft (if draft is not already kept)."""
    reg = registry_dir(root)
    kept = kept_palette_ids(reg)
    session = load_iteration_session(reg)
    draft = session.get("draft_palette_id")
    ids = list(dict.fromkeys(kept + ([draft] if draft and draft not in kept else [])))
    return sorted(ids)


def record_draft(root: Path, palette_id: str, prompt: str, *, derived_from: str | None) -> None:
    reg = registry_dir(root)
    session = load_iteration_session(reg)
    chain = list(session.get("chain") or [])
    if derived_from and derived_from not in chain:
        chain.append(derived_from)
    if palette_id not in chain:
        chain.append(palette_id)
    session["draft_palette_id"] = palette_id
    session["chain"] = chain
    session["last_prompt"] = prompt
    session["updated_at"] = _iso_now()
    save_iteration_session(reg, session)


def load_palette(root: Path, palette_id: str) -> dict[str, Any]:
    path = root / "outputs" / "palettes" / f"{palette_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Palette not found: {path}")
    return enrich_legacy_palette(json.loads(path.read_text(encoding="utf-8")))


def discard_ide_palette(root: Path, palette_id: str) -> dict[str, Any]:
    """Remove from export roster (unwanted / dropped). Palette JSON may remain on disk."""
    from core.ide_theme import finalize_ide_themes

    reg = registry_dir(root)
    roster_remove(reg, palette_id)
    session = load_iteration_session(reg)
    if session.get("draft_palette_id") == palette_id:
        session["draft_palette_id"] = None
        save_iteration_session(reg, session)
    export = finalize_ide_themes(root)
    return {"palette_id": palette_id, "discarded": True, "export": export}


def keep_ide_palette(root: Path, palette_id: str, *, prompt: str | None = None) -> dict[str, Any]:
    """User likes this one — add to export roster and reinstall extension."""
    from core.ide_theme import finalize_ide_themes

    palette_dir = root / "outputs" / "palettes"
    reg = registry_dir(root)
    pal = load_palette(root, palette_id)
    roster_add(reg, palette_dir, palette_id, prompt=prompt or pal.get("user_prompt"))
    session = load_iteration_session(reg)
    session["draft_palette_id"] = palette_id
    save_iteration_session(reg, session)
    export = finalize_ide_themes(root)
    return {
        "palette_id": palette_id,
        "theme_name": pal.get("theme_name"),
        "kept": True,
        "export": export,
        "installed": bool(export.get("installed")),
    }


def iterate_ide_palette(
    root: Path,
    prompt: str,
    *,
    from_palette_id: str | None = None,
    style: str | None = None,
    name: str | None = None,
    is_light: bool | None = None,
) -> dict[str, Any]:
    """Next attempt in a chat iteration — inherits prior slot, new id, auto ships."""
    from core.ide_theme import make_ide_palette

    reg = registry_dir(root)
    session = load_iteration_session(reg)
    parent_id = from_palette_id or session.get("draft_palette_id")
    variety, adherence = 0.55, 0.75
    resolved_style = style or infer_style_from_prompt(prompt)

    if parent_id:
        parent = load_palette(root, parent_id)
        meta = palette_meta(parent)
        resolved_style = style or str(parent.get("style_archetype") or meta["style_archetype"])
        if is_light is None:
            is_light = bool(parent.get("is_light", meta["is_light"]))
        gc = parent.get("generation_controls") or {}
        variety = float(gc.get("chromatic_variety", variety))
        adherence = float(gc.get("prompt_adherence", adherence))
        variety, adherence = _tweak_controls_from_feedback(prompt, variety, adherence)
        iteration_index = int(parent.get("iteration_index", 0)) + 1
    else:
        iteration_index = 1

    return make_ide_palette(
        root,
        prompt,
        style=resolved_style,
        is_light=is_light,
        name=name,
        variety=variety,
        adherence=adherence,
        derived_from=parent_id,
        iteration_index=iteration_index,
    )
