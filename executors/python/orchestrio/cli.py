# Copyright 2026 NetApp, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    """Orchestrio — workflow executor."""
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


if __name__ == "__main__":
    cli()
