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
from orchestrio.env_loader import EnvLoadError, load_env_file, merge_env, parse_env_pairs
from orchestrio.models import WorkflowStatus
from orchestrio.parser import load_workflow
from orchestrio.run_logger import RunLogger


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
@click.option(
    "--env-file", "-E",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Load env vars from a file (.env, .yaml, .json). Repeatable; later files override earlier ones.",
)
@click.option(
    "--env", "-e",
    multiple=True,
    metavar="KEY=VALUE",
    help="Set an env var inline. Repeatable; overrides --env-file and YAML defaults.",
)
@click.option(
    "--log-file", "-L",
    type=click.Path(path_type=Path),
    default=None,
    help="Path for the structured JSONL log file.  Defaults to logs/run-<id>.log.jsonl.",
)
@click.option(
    "--no-log",
    is_flag=True,
    default=False,
    help="Disable JSONL log file output entirely.",
)
def run(
    file: Path,
    dry_run: bool,
    env_file: tuple[Path, ...],
    env: tuple[str, ...],
    log_file: Path | None,
    no_log: bool,
) -> None:
    """Execute a workflow from a YAML / JSON file."""
    workflow = load_workflow(file)

    try:
        env_file_vars: dict[str, str] = {}
        for ef in env_file:
            env_file_vars.update(load_env_file(ef))
        cli_env_vars = parse_env_pairs(env)
    except EnvLoadError as exc:
        raise click.BadParameter(str(exc)) from exc

    workflow.env = merge_env(workflow.env, env_file_vars, cli_env_vars)

    if dry_run or no_log:
        result = asyncio.run(run_workflow(workflow, dry_run=dry_run))
    else:
        import uuid
        run_id = uuid.uuid4().hex[:12]
        if log_file:
            resolved_log = log_file
        else:
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            resolved_log = logs_dir / f"run-{run_id}.log.jsonl"
        with RunLogger(resolved_log, run_id) as rlog:
            result = asyncio.run(run_workflow(workflow, dry_run=dry_run, run_log=rlog))
        click.echo(f"Log written to {resolved_log}", err=True)

    if not dry_run:
        click.echo(result.model_dump_json(indent=2))
    sys.exit(0 if result.status == WorkflowStatus.SUCCESS else 1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--env-file", "-E",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Load env vars from a file (.env, .yaml, .json). Repeatable.",
)
@click.option(
    "--env", "-e",
    multiple=True,
    metavar="KEY=VALUE",
    help="Set an env var inline. Repeatable.",
)
def validate(file: Path, env_file: tuple[Path, ...], env: tuple[str, ...]) -> None:
    """Validate a workflow file without executing it."""
    try:
        workflow = load_workflow(file)

        env_file_vars: dict[str, str] = {}
        for ef in env_file:
            env_file_vars.update(load_env_file(ef))
        cli_env_vars = parse_env_pairs(env)
        workflow.env = merge_env(workflow.env, env_file_vars, cli_env_vars)

        click.echo(f"✓ Valid workflow: {workflow.name} ({len(workflow.steps)} steps)")

        for rec in workflow.include_meta:
            click.echo(f"  ↳ Step '{rec.step_name}' included from {rec.include_path}")

        if workflow.defaults:
            step_types = {s.type for s in workflow.steps}
            for default_type in workflow.defaults:
                if default_type not in step_types:
                    click.echo(
                        f"  ⚠ defaults.{default_type}: no steps of type "
                        f"'{default_type}' in this workflow",
                        err=True,
                    )
    except EnvLoadError as exc:
        click.echo(f"✗ Invalid env: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"✗ Invalid: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
