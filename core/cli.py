"""Typer CLI for RobRoss Palette OS."""

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
from core.generate import build_superset_from_palettes, generate_palettes
from core.genome import default_genome, ensure_genome_dir, load_genome, merge_genomes, save_genome
from core.ingest import ingest_source
from core.preview_html import build_preview_page, load_ide_palettes_from_dir
from core.prompt_brief import apply_prompt_archetype_order, genome_patch_from_prompt
from core.roster import (
    apply_roster_learning_to_disk,
    load_roster,
    roster_add,
    roster_path,
    roster_remove,
)

app = typer.Typer(help="RobRoss Palette OS CLI")
roster_app = typer.Typer(help="Curate palettes for export and teach the genome from picks")
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
def generate(task: str = typer.Option(..., "--task", help="Natural language generation task")) -> None:
    """Generate palettes from the current genome."""
    root = _project_root()
    gpath = _genome_path()
    if not gpath.exists():
        typer.echo("Genome not found. Run build-genome first.")
        raise typer.Exit(code=1)
    genome = load_genome(gpath)
    result = generate_palettes(task, genome, root / "outputs" / "palettes")

    report_path = root / "outputs" / "reports" / f"generation_report_{result['generated_count']}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# Generation Report",
        "",
        f"- Generated count: {result['generated_count']}",
        f"- Task plan: `{result['task_plan']}`",
        "",
    ]
    for p in result["palettes"]:
        report_lines.append(f"## {p['id']}")
        report_lines.append(p["palette_rationale"])
        report_lines.append("")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    subprocess.run([sys.executable, str(root / "scripts" / "export_vscode_themes.py")], check=True, cwd=root)

    console.print("[green]Generation complete.[/green]")
    console.print(f"Palettes dir: {root / 'outputs' / 'palettes'}")
    console.print(f"Report: {report_path}")
    console.print(f"VSIX dir: {root / 'vscode-themes'}")


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


@app.command()
def quick(
    prompt: str = typer.Argument(..., help='Short color brief, e.g. "black and yellow"'),
    count: int = typer.Option(4, "--count", "-n", help="How many IDE palette variants"),
    export: bool = typer.Option(False, "--export", help="Run export-themes after generation"),
) -> None:
    """Generate a few IDE themes from a plain-language color prompt (session-only genome tweaks)."""
    root = _project_root()
    gpath = _genome_path()
    if not gpath.exists():
        typer.echo("Genome not found. Copy or create genome/genome_v1.json first.")
        raise typer.Exit(code=1)
    base = load_genome(gpath)
    patch = genome_patch_from_prompt(prompt)
    merged, _conf = merge_genomes(base, patch)
    apply_prompt_archetype_order(merged)
    task = f"make {count} ide palettes"
    result = generate_palettes(task, merged, root / "outputs" / "palettes", user_prompt=prompt)

    report_path = root / "outputs" / "reports" / f"quick_{result['generated_count']}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Quick generation",
        "",
        f"- Prompt: {prompt}",
        f"- Variants: {count}",
        f"- Task plan: `{result['task_plan']}`",
        "",
    ]
    for p in result["palettes"]:
        lines.append(f"## {p['id']}")
        lines.append(p.get("palette_rationale", ""))
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    console.print("[green]Quick batch ready.[/green]")
    console.print(f"Palettes: {root / 'outputs' / 'palettes'}")
    console.print(f"Report: {report_path}")
    console.print("Preview in browser: [cyan]python cli.py preview[/cyan]")
    console.print("Add keepers: [cyan]python cli.py roster add ide_palette_02 --prompt \"...\"[/cyan]")
    if export:
        export_themes(all_palettes=False)


@app.command()
def preview(
    roster_only: bool = typer.Option(
        False,
        "--roster-only",
        help="Only palettes listed in genome/theme_roster.json (if non-empty)",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open/--no-open",
        help="Open the HTML file in your default browser",
    ),
) -> None:
    """Generate a browser preview gallery of IDE palettes (mock editor + syntax colors)."""
    root = _project_root()
    palette_dir = root / "outputs" / "palettes"
    ids: list[str] | None = None
    if roster_only:
        data = load_roster(root / "genome")
        ids = list(data.get("palette_ids") or [])
        if not ids:
            console.print("[yellow]Roster empty; showing all ide_palette_*.json instead.[/yellow]")
            ids = None
    palettes = load_ide_palettes_from_dir(palette_dir, ids)
    if not palettes:
        typer.echo(f"No IDE palettes found under {palette_dir}")
        raise typer.Exit(code=1)
    out = root / "outputs" / "preview" / "index.html"
    build_preview_page(palettes, out)
    console.print(f"[green]Preview written:[/green] {out}")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())


@app.command("export-themes")
def export_themes(
    all_palettes: bool = typer.Option(False, "--all", help="Export every ide_palette_*.json (ignore roster)"),
) -> None:
    """Build vscode-themes/ from disk. Uses genome/theme_roster.json when it lists palette IDs."""
    root = _project_root()
    cmd = [sys.executable, str(root / "scripts" / "export_vscode_themes.py")]
    rp = roster_path(root / "genome")
    if not all_palettes and rp.exists():
        data = load_roster(root / "genome")
        if data.get("palette_ids"):
            cmd.extend(["--roster", str(rp)])
    subprocess.run(cmd, check=True, cwd=root)
    console.print("[green]Theme extension updated.[/green]")
    console.print(f"VSIX / themes: {root / 'vscode-themes'}")


@roster_app.command("add")
def roster_add_cmd(
    palette_id: str = typer.Argument(..., help="e.g. ide_palette_03"),
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Original quick prompt (for learning metadata)"),
    learn: bool = typer.Option(True, "--learn/--no-learn", help="Update genome from full roster"),
) -> None:
    root = _project_root()
    gdir = root / "genome"
    palette_dir = root / "outputs" / "palettes"
    roster_add(gdir, palette_dir, palette_id, prompt=prompt)
    console.print(f"[green]Added[/green] {palette_id} to roster ({roster_path(gdir)})")
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
