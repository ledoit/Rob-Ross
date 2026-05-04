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
