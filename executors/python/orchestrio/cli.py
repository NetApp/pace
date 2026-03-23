"""CLI entry point for Orchestrio."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

from orchestrio.engine import run_workflow
from orchestrio.models import WorkflowStatus
from orchestrio.parser import load_workflow


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """Orchestrio — REST API workflow executor."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, default=False, help="Resolve templates and print steps without executing.")
def run(file: Path, dry_run: bool) -> None:
    """Execute a workflow from a YAML / JSON file."""
    workflow = load_workflow(file)
    result = asyncio.run(run_workflow(workflow, dry_run=dry_run))
    if not dry_run:
        click.echo(result.model_dump_json(indent=2))
    sys.exit(0 if result.status == WorkflowStatus.SUCCESS else 1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def validate(file: Path) -> None:
    """Validate a workflow file without executing it."""
    try:
        workflow = load_workflow(file)
        click.echo(f"✓ Valid workflow: {workflow.name} ({len(workflow.steps)} steps)")
    except Exception as exc:
        click.echo(f"✗ Invalid: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", default=8000, type=int, help="Port number.")
def serve(host: str, port: int) -> None:
    """Start the REST API server."""
    import uvicorn

    uvicorn.run("orchestrio.api.app:app", host=host, port=port)


if __name__ == "__main__":
    cli()
