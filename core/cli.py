"""Typer CLI for Rob Ross palette OS."""

from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.pretty import pprint

from core.feedback import collect_feedback, maybe_apply_feedback_to_genome
from core.generate import build_superset_from_palettes
from core.genome import default_genome, ensure_genome_dir, load_genome, merge_genomes, save_genome
from core.ingest import ingest_source
from core.roster import (
    apply_roster_learning_to_disk,
    load_roster,
    roster_add,
    roster_path,
    roster_remove,
)
from core.harmony import HARMONY_MODES, describe_harmony
from core.export.css_site_tokens import export_all_web_palettes, export_palette_file
from core.export.consumer_sync import load_consumers, sync_consumer
from core.pathways.web_sites import SITE_PROFILES
from core.preview_web_html import build_web_preview_page, load_web_palettes_from_dir
from core.ide_theme import run_theme_export
from core.web_session import run_web_quick

app = typer.Typer(help="Rob Ross palette OS CLI")
web_app = typer.Typer(help="Website palettes — harmonies, CSS export, consumer sync")
app.add_typer(web_app, name="web")
roster_app = typer.Typer(help="IDE export roster (prefer keep_ide_palette in chat)")
app.add_typer(roster_app, name="roster")
console = Console()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _genome_path() -> Path:
    return _project_root() / "genome" / "genome_v1.json"


@app.command()
def ingest(source: str) -> None:
    """Ingest URL, file path, PDF text, or raw hex source."""
    root = _project_root()
    result = ingest_source(source, root)
    console.print("[green]Ingestion complete.[/green]")
    pprint(result)


@app.command("build-genome")
def build_genome() -> None:
    """Build or update genome from processed principle chunks."""
    root = _project_root()
    genome_dir = ensure_genome_dir(root / "genome")
    gpath = genome_dir / "genome_v1.json"

    current = load_genome(gpath) if gpath.exists() else default_genome()
    processed_files = sorted((root / "sources" / "processed").glob("principles_*.json"))
    aggregate_updates = {"sources_ingested": list(current.get("sources_ingested", []))}

    for p in processed_files:
        rows = json.loads(p.read_text(encoding="utf-8"))
        for row in rows:
            src = row.get("source_id")
            if src and src not in aggregate_updates["sources_ingested"]:
                aggregate_updates["sources_ingested"].append(src)

    merged, conflicts = merge_genomes(current, aggregate_updates)
    merged.setdefault("conflict_resolutions", [])
    for c in conflicts:
        merged["conflict_resolutions"].append(
            {
                "conflict": f"{c['path']} mismatch",
                "resolution": c["resolution"],
                "source": "aggregate_updates",
                "notes": "Auto-merged during build-genome.",
            }
        )

    save_genome(merged, gpath, genome_dir / "genome_history")
    console.print("[green]Genome built and saved.[/green]")
    console.print(f"Path: {gpath}")
    console.print(f"Conflicts flagged: {len(conflicts)}")


@app.command()
def feedback() -> None:
    """Collect ratings and optionally update genome."""
    root = _project_root()
    gpath = _genome_path()
    if not gpath.exists():
        typer.echo("Genome not found. Run build-genome first.")
        raise typer.Exit(code=1)
    genome = load_genome(gpath)

    rows = collect_feedback(root / "outputs" / "palettes")
    if not rows:
        typer.echo("No palettes found to rate.")
        raise typer.Exit(code=1)

    updated, diffs, applied = maybe_apply_feedback_to_genome(genome, rows)
    console.print(f"Proposed genome diffs: {len(diffs)}")
    for d in diffs:
        console.print(f"- {d['path']}: {d['old']} -> {d['new']}")

    if applied:
        save_genome(updated, gpath, root / "genome" / "genome_history")
        console.print("[green]Genome updated from feedback.[/green]")
    else:
        console.print("[yellow]Genome unchanged.[/yellow]")


@web_app.command("quick")
def web_quick(
    prompt: str = typer.Argument(..., help='Brief, e.g. "editorial dark minimal gold accent"'),
    count: int = typer.Option(4, "--count", "-n", help="Palette variants"),
    site: str = typer.Option(
        "generic",
        "--site",
        "-s",
        help="reno | jobjeeves | photoport | paid | generic",
    ),
    harmony: str | None = typer.Option(
        None,
        "--harmony",
        "-H",
        help=f"Override site default harmony: {', '.join(HARMONY_MODES)}",
    ),
    variety: float | None = typer.Option(None, "--variety", min=0.0, max=1.0),
    adherence: float | None = typer.Option(None, "--adherence", min=0.0, max=1.0),
    seed_from: str | None = typer.Option(
        None,
        "--seed-from",
        help="Roster palette id to breed from (e.g. web_photoport_palette_01)",
    ),
) -> None:
    """Generate website palettes (WCAG roles + site profiles). IDE not touched."""
    root = _project_root()
    if harmony and harmony not in HARMONY_MODES:
        typer.echo(f"Unknown harmony. Choose: {', '.join(HARMONY_MODES)}")
        raise typer.Exit(code=1)
    result = run_web_quick(
        root,
        prompt,
        count=count,
        site=site,
        harmony=harmony,
        variety=variety,
        adherence=adherence,
        seed_from=seed_from,
    )
    if result.get("scratch_kept"):
        console.print(f"[cyan]Kept (roster):[/cyan] {', '.join(result['scratch_kept'])}")
    if result.get("scratch_removed"):
        console.print(f"[dim]Replaced scratch:[/dim] {', '.join(result['scratch_removed'])}")
    console.print("[green]Web batch ready.[/green]")
    console.print(f"Palettes: {root / 'outputs' / 'palettes'}")
    console.print(f"Report: {result['report_path']}")
    console.print("Preview: [cyan]python cli.py web preview --site " + site + "[/cyan]")
    console.print("Export CSS: [cyan]python cli.py web export --all[/cyan]")


@web_app.command("preview")
def web_preview(
    site: str | None = typer.Option(None, "--site", "-s", help="Filter by site profile"),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Landing-page mock gallery for web_* palettes."""
    root = _project_root()
    palette_dir = root / "outputs" / "palettes"
    palettes = load_web_palettes_from_dir(palette_dir, site)
    if not palettes:
        typer.echo(f"No web palettes under {palette_dir}. Run: python cli.py web quick \"…\"")
        raise typer.Exit(code=1)
    out = root / "outputs" / "preview" / "web.html"
    build_web_preview_page(palettes, out)
    console.print(f"[green]Web preview:[/green] {out}")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())


@web_app.command("export")
def web_export(
    palette_id: str | None = typer.Argument(None, help="e.g. web_reno_palette_01 (omit with --all)"),
    site: str | None = typer.Option(None, "--site", "-s"),
    all_palettes: bool = typer.Option(False, "--all", help="Export every web_*_palette_*.json"),
) -> None:
    """Write CSS partials to outputs/web-tokens/{site}/."""
    root = _project_root()
    palette_dir = root / "outputs" / "palettes"
    out_dir = root / "outputs" / "web-tokens"
    if all_palettes:
        paths = export_all_web_palettes(palette_dir, out_dir)
        if not paths:
            typer.echo("No web_*_palette_*.json files found.")
            raise typer.Exit(code=1)
        for p in paths:
            console.print(f"[green]Wrote[/green] {p}")
        return
    if not palette_id:
        typer.echo("Provide palette_id or use --all")
        raise typer.Exit(code=1)
    src = palette_dir / f"{palette_id.replace('.json', '')}.json"
    if not src.is_file():
        typer.echo(f"Not found: {src}")
        raise typer.Exit(code=1)
    path = export_palette_file(src, out_dir, site=site)
    console.print(f"[green]Wrote[/green] {path}")


@web_app.command("sites")
def web_sites() -> None:
    """List website profiles (brand-lock, default harmony)."""
    for key, prof in SITE_PROFILES.items():
        console.print(
            f"[bold]{key}[/bold] — {prof.get('label')} "
            f"(harmony: {prof.get('harmony_default')}, brand_lock: {prof.get('brand_lock')})"
        )


@web_app.command("harmonies")
def web_harmonies() -> None:
    """Coolors-style harmony modes (hue geometry)."""
    for mode in HARMONY_MODES:
        console.print(f"[bold]{mode}[/bold] — {describe_harmony(mode)}")


@web_app.command("consumers")
def web_consumers() -> None:
    """List registered downstream sites (genome/web_consumers.json)."""
    root = _project_root()
    reg = load_consumers(root / "genome")
    for key, spec in sorted((reg.get("consumers") or {}).items()):
        console.print(f"[bold]{key}[/bold] — {spec.get('label', '')} → {spec.get('path')}")


@web_app.command("sync")
def web_sync(
    consumer: str = typer.Argument(..., help="Consumer id from web consumers registry (e.g. paid)"),
    all_palettes: bool = typer.Option(
        False,
        "--all",
        help="Sync every ide_palette_*.json on disk (ignore roster)",
    ),
) -> None:
    """Push kept IDE palettes into a registered website consumer (TypeScript, etc.)."""
    root = _project_root()
    try:
        result = sync_consumer(root, consumer, roster_only=not all_palettes)
    except (KeyError, FileNotFoundError, ValueError) as e:
        typer.echo(str(e))
        raise typer.Exit(code=1) from e
    console.print(f"[green]Synced[/green] {result['theme_count']} themes -> {result['path']}")
    console.print(f"Palette ids: {', '.join(result['palette_ids'])}")


@app.command("export-themes")
def export_themes(
    all_palettes: bool = typer.Option(False, "--all", help="Export every ide_palette_*.json (ignore roster)"),
) -> None:
    """Build vscode-themes/ from disk. Uses genome/theme_roster.json when it lists palette IDs."""
    root = _project_root()
    run_theme_export(root, all_palettes=all_palettes)
    console.print("[green]Theme extension updated.[/green]")
    console.print(f"VSIX / themes: {root / 'vscode-themes'}")



@roster_app.command("add")
@roster_app.command("export-add")
def roster_add_cmd(
    palette_id: str = typer.Argument(..., help="e.g. ide_palette_03"),
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Original quick prompt (for learning metadata)"),
    learn: bool = typer.Option(True, "--learn/--no-learn", help="Update genome from full export roster"),
) -> None:
    """Final pick: this theme is included when you run export-themes (and VSIX packaging)."""
    root = _project_root()
    gdir = root / "genome"
    palette_dir = root / "outputs" / "palettes"
    _data, bump = roster_add(gdir, palette_dir, palette_id, prompt=prompt)
    console.print(f"[green]Added[/green] {palette_id} to export roster ({roster_path(gdir)})")
    if bump:
        console.print(f"[dim]Taste weights: {bump}[/dim]")
    if learn:
        stats = apply_roster_learning_to_disk(
            gdir / "genome_v1.json",
            gdir / "genome_history",
            load_roster(gdir),
            palette_dir,
        )
        console.print(f"Learning: {stats}")


@roster_app.command("remove")
def roster_remove_cmd(palette_id: str = typer.Argument(...)) -> None:
    root = _project_root()
    gdir = root / "genome"
    roster_remove(gdir, palette_id)
    console.print(f"[green]Removed[/green] {palette_id} from roster")


@roster_app.command("list")
def roster_list_cmd() -> None:
    root = _project_root()
    data = load_roster(root / "genome")
    if not data.get("palette_ids"):
        console.print("Roster is empty (export-themes will use all ide palettes).")
        return
    for pid in data["palette_ids"]:
        meta = data.get("entries", {}).get(pid, {})
        p = meta.get("prompt", "")
        console.print(f"- [bold]{pid}[/bold]" + (f" — {p}" if p else ""))


@roster_app.command("learn")
def roster_learn_cmd() -> None:
    """Re-run genome update from the current roster (no add/remove)."""
    root = _project_root()
    gdir = root / "genome"
    stats = apply_roster_learning_to_disk(
        gdir / "genome_v1.json",
        gdir / "genome_history",
        load_roster(gdir),
        root / "outputs" / "palettes",
    )
    console.print(stats)


@app.command()
def superset(
    input_palettes: str = typer.Option("outputs/palettes", "--input-palettes"),
    count: int = typer.Option(25, "--count"),
) -> None:
    """Build a deduplicated megapalette from generated palettes."""
    root = _project_root()
    source_dir = root / input_palettes
    result = build_superset_from_palettes(source_dir, count=count)
    out_path = root / "outputs" / "palettes" / f"superset_{count}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    console.print("[green]Superset generated.[/green]")
    console.print(f"Saved: {out_path}")
    console.print(result["coverage_analysis"])


if __name__ == "__main__":
    app()
