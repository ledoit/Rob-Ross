"""Typer CLI for RobRoss Palette OS."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.pretty import pprint

from core.feedback import collect_feedback, maybe_apply_feedback_to_genome
from core.generate import build_superset_from_palettes, generate_palettes
from core.genome import default_genome, ensure_genome_dir, load_genome, merge_genomes, save_genome
from core.ingest import ingest_source

app = typer.Typer(help="RobRoss Palette OS CLI")
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
