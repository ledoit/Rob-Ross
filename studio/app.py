"""Rob Ross Palette Studio — local-first infinite regen loop UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from core.genome import load_genome
from core.preview_html import build_preview_page, load_ide_palettes_from_dir
from core.quick_session import list_ide_palette_meta, run_quick
from core.roster import apply_roster_learning_to_disk, load_roster, roster_add
from core.user_loop import ensure_user_loop_state, state_path as user_loop_state_path
from core.export.css_site_tokens import export_all_web_palettes, export_palette_file, palette_to_css
from core.studio_web import (
    editable_roles_for_site,
    list_saved_web_palettes,
    list_web_palette_meta,
    load_palette_file,
    palette_to_generate_params,
    rebuild_gallery_preview,
    set_role_hex,
    studio_boot_payload,
    tweak_palette,
)
from core.web_session import run_web_quick

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
TEMPLATES = Path(__file__).resolve().parent / "templates"

app = FastAPI(
    title="Rob Ross Palette Studio",
    description="Select → regenerate → heart. Local only.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES))


def _genome_dir() -> Path:
    return ROOT / "genome"


def _palette_dir() -> Path:
    return ROOT / "outputs" / "palettes"


def _ensure_genome() -> None:
    g = _genome_dir() / "genome_v1.json"
    if not g.is_file():
        raise HTTPException(status_code=503, detail=f"Missing genome: {g}")


def _rebuild_preview() -> Path:
    palette_dir = _palette_dir()
    palettes = load_ide_palettes_from_dir(palette_dir, None)
    out = ROOT / "outputs" / "preview" / "index.html"
    build_preview_page(palettes, out, title="Rob Ross palette preview — Studio")
    return out


class RegenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    count: int = Field(4, ge=1, le=12)
    variety: float | None = Field(None, ge=0.0, le=1.0)
    adherence: float | None = Field(None, ge=0.0, le=1.0)
    fresh: bool = True
    """When True, replace roster shortlist with shortlist_ids (empty list clears). When False, leave shortlist as-is."""
    use_selection_as_shortlist: bool = True
    shortlist_ids: list[str] = Field(default_factory=list)
    export_themes: bool = False


class HeartBody(BaseModel):
    palette_id: str = Field(..., min_length=1)
    prompt: str | None = Field(None, max_length=2000)
    learn: bool = True


class WebRegenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    count: int = Field(4, ge=1, le=12)
    site: str = Field("generic", max_length=64)
    harmony: str | None = Field(None, max_length=32)
    variety: float | None = Field(None, ge=0.0, le=1.0)
    adherence: float | None = Field(None, ge=0.0, le=1.0)
    seed_from: str | None = Field(None, max_length=128, description="Roster palette id to breed the next scratch batch from")


class WebTweakBody(BaseModel):
    palette_id: str = Field(..., min_length=1)
    action: str = Field(..., pattern="^(reroll|hue_nudge|set_harmony)$")
    harmony: str | None = None
    hue_delta: float | None = None


class WebRoleBody(BaseModel):
    palette_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1, max_length=64)
    hex: str = Field(..., min_length=4, max_length=32)


class WebExportBody(BaseModel):
    palette_id: str | None = None
    all: bool = False


@app.get("/web", response_class=HTMLResponse)
def web_studio_home(request: Request, site: str | None = None) -> HTMLResponse:
    _ensure_genome()
    boot = studio_boot_payload(ROOT, site=site)
    return templates.TemplateResponse(
        request,
        "web_studio.html",
        {"boot_json": json.dumps(boot)},
    )


@app.get("/api/web/saved")
def api_web_saved() -> JSONResponse:
    _ensure_genome()
    return JSONResponse({"saved": list_saved_web_palettes(_genome_dir(), _palette_dir())})


@app.get("/api/web/saved/{palette_id}/params")
def api_web_saved_params(palette_id: str) -> JSONResponse:
    _ensure_genome()
    gdir = _genome_dir()
    roster = load_roster(gdir)
    if palette_id not in (roster.get("palette_ids") or []):
        raise HTTPException(status_code=404, detail="Palette not on roster (Save it first)")
    try:
        pal = load_palette_file(_palette_dir(), palette_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return JSONResponse({"params": palette_to_generate_params(pal)})


@app.get("/api/web/palettes")
def api_web_palettes(site: str | None = None) -> JSONResponse:
    _ensure_genome()
    return JSONResponse({"palettes": list_web_palette_meta(_palette_dir(), site)})


@app.get("/api/web/palette/{palette_id}")
def api_web_palette_one(palette_id: str) -> JSONResponse:
    _ensure_genome()
    try:
        pal = load_palette_file(_palette_dir(), palette_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    pal["_editable_roles"] = editable_roles_for_site(pal.get("site"))
    return JSONResponse(pal)


@app.get("/api/web/css/{palette_id}")
def api_web_css(palette_id: str) -> JSONResponse:
    _ensure_genome()
    try:
        pal = load_palette_file(_palette_dir(), palette_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return JSONResponse({"css": palette_to_css(pal, site=pal.get("site"))})


@app.post("/api/web/regenerate")
def api_web_regenerate(body: WebRegenerateBody) -> JSONResponse:
    _ensure_genome()
    try:
        result = run_web_quick(
            ROOT,
            body.prompt.strip(),
            count=body.count,
            site=body.site,
            harmony=body.harmony,
            variety=body.variety,
            adherence=body.adherence,
            seed_from=body.seed_from,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rebuild_gallery_preview(ROOT)
    return JSONResponse(
        {
            "ok": True,
            "generated_count": result["generated_count"],
            "scratch_removed": result.get("scratch_removed") or [],
            "scratch_kept": result.get("scratch_kept") or [],
            "seed_from": result.get("seed_from"),
            "palettes": list_web_palette_meta(_palette_dir(), body.site),
        }
    )


@app.post("/api/web/tweak")
def api_web_tweak(body: WebTweakBody) -> JSONResponse:
    _ensure_genome()
    try:
        pal = tweak_palette(
            _palette_dir(),
            _genome_dir() / "genome_v1.json",
            body.palette_id,
            action=body.action,
            harmony=body.harmony,
            hue_delta=body.hue_delta,
            genome_dir=_genome_dir(),
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rebuild_gallery_preview(ROOT)
    meta = pal.pop("_studio_meta", None) or {}
    return JSONResponse({"ok": True, "palette": pal, **meta})


@app.post("/api/web/role")
def api_web_role(body: WebRoleBody) -> JSONResponse:
    _ensure_genome()
    try:
        pal = set_role_hex(
            _palette_dir(),
            body.palette_id,
            body.role,
            body.hex,
            genome_dir=_genome_dir(),
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return JSONResponse({"ok": True, "palette": pal})


@app.post("/api/web/save")
def api_web_save(body: HeartBody) -> JSONResponse:
    """Pin palette to roster so the next Generate keeps it (scratch-safe)."""
    _ensure_genome()
    gdir = _genome_dir()
    try:
        _data, bump = roster_add(
            gdir,
            _palette_dir(),
            body.palette_id,
            prompt=body.prompt,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    r = load_roster(gdir)
    return JSONResponse(
        {
            "ok": True,
            "palette_id": body.palette_id,
            "export_ids": r.get("palette_ids") or [],
            "bump": bump,
        }
    )


@app.post("/api/web/export")
def api_web_export(body: WebExportBody) -> JSONResponse:
    _ensure_genome()
    out_dir = ROOT / "outputs" / "web-tokens"
    if body.all:
        paths = export_all_web_palettes(_palette_dir(), out_dir)
        return JSONResponse({"ok": True, "paths": [str(p) for p in paths]})
    if not body.palette_id:
        raise HTTPException(status_code=400, detail="palette_id or all=true required")
    src = _palette_dir() / f"{body.palette_id.replace('.json', '')}.json"
    if not src.is_file():
        raise HTTPException(status_code=404, detail=f"Not found: {src}")
    path = export_palette_file(src, out_dir)
    return JSONResponse({"ok": True, "path": str(path)})


@app.get("/web/preview")
def web_preview_page() -> FileResponse:
    _ensure_genome()
    path = rebuild_gallery_preview(ROOT)
    return FileResponse(path, media_type="text/html", headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse)
def studio_home(request: Request) -> HTMLResponse:
    _ensure_genome()
    gdir = _genome_dir()
    base = load_genome(gdir / "genome_v1.json")
    ensure_user_loop_state(user_loop_state_path(gdir), base)
    roster = load_roster(gdir)
    palettes = list_ide_palette_meta(_palette_dir())
    seed_hint = os.environ.get("ROB_ROSS_SEED", "").strip()
    boot = {
        "palettes": palettes,
        "roster": {
            "export_ids": roster.get("palette_ids") or [],
            "shortlist_ids": roster.get("shortlist_ids") or [],
        },
        "seed_active": bool(seed_s.isdigit() if (seed_s := seed_hint) else False),
    }
    return templates.TemplateResponse(
        request,
        "studio.html",
        {
            "boot_json": json.dumps(boot),
        },
    )


@app.get("/api/palettes")
def api_palettes() -> JSONResponse:
    _ensure_genome()
    return JSONResponse({"palettes": list_ide_palette_meta(_palette_dir())})


@app.get("/api/roster")
def api_roster() -> JSONResponse:
    _ensure_genome()
    r = load_roster(_genome_dir())
    return JSONResponse(
        {
            "export_ids": r.get("palette_ids") or [],
            "shortlist_ids": r.get("shortlist_ids") or [],
        }
    )


@app.post("/api/regenerate")
def api_regenerate(body: RegenerateBody) -> JSONResponse:
    _ensure_genome()
    try:
        sp = body.shortlist_ids if body.use_selection_as_shortlist else None
        result = run_quick(
            ROOT,
            body.prompt.strip(),
            count=body.count,
            variety=body.variety,
            adherence=body.adherence,
            export_themes=body.export_themes,
            fresh=body.fresh,
            shortlist_palette_ids=sp,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _rebuild_preview()
    ids = [p.get("id") for p in result.get("palettes") or [] if p.get("id")]
    r = load_roster(_genome_dir())
    return JSONResponse(
        {
            "ok": True,
            "generated_count": result["generated_count"],
            "palette_ids": ids,
            "shortlist_bias": result.get("shortlist_bias"),
            "fresh_removed": result.get("fresh_removed", 0),
            "palettes": list_ide_palette_meta(_palette_dir()),
            "roster": {
                "export_ids": r.get("palette_ids") or [],
                "shortlist_ids": r.get("shortlist_ids") or [],
            },
        }
    )


@app.post("/api/heart")
def api_heart(body: HeartBody) -> JSONResponse:
    _ensure_genome()
    gdir = _genome_dir()
    palette_dir = _palette_dir()
    try:
        _data, bump = roster_add(
            gdir,
            palette_dir,
            body.palette_id,
            prompt=body.prompt,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    learn_stats: dict[str, Any] | None = None
    if body.learn:
        learn_stats = apply_roster_learning_to_disk(
            gdir / "genome_v1.json",
            gdir / "genome_history",
            load_roster(gdir),
            palette_dir,
        )
    _rebuild_preview()
    r = load_roster(gdir)
    return JSONResponse(
        {
            "ok": True,
            "palette_id": body.palette_id,
            "bump": bump,
            "learn": learn_stats,
            "export_ids": r.get("palette_ids") or [],
        }
    )


@app.get("/preview/latest")
def preview_latest() -> FileResponse:
    _ensure_genome()
    _rebuild_preview()
    path = ROOT / "outputs" / "preview" / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Preview not built")
    return FileResponse(
        path,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rob-ross-studio"}
