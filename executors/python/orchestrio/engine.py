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

"""Workflow execution engine.

Responsibilities:
    • Execute steps sequentially
    • Resolve {{ steps.<name>.<path> }} and {{ env.<key> }} templates between steps
    • Retry failed steps per their retry config
    • Honour on_failure (stop / continue) semantics
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from orchestrio.models import (
    OnFailure,
    StepDefinition,
    StepResult,
    StepStatus,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowStatus,
)
from orchestrio.plugins.base import get_plugin
from orchestrio.utils import deep_merge, walk_path

logger = logging.getLogger("orchestrio.engine")

# ── Template resolution ────────────────────────────────────────────

# Matches {{ steps.stepName.field.subfield }}
_TEMPLATE_RE = re.compile(r"\{\{\s*steps\.(\w+)((?:\.\w+)+)\s*\}\}")

# Matches {{ env.VAR_NAME }}
_ENV_RE = re.compile(r"\{\{\s*env\.(\w+)\s*\}\}")


def _resolve_ref(context: dict[str, Any], step_name: str, dotted_path: str) -> Any:
    """Walk a dotted path inside a step's stored output."""
    return walk_path(context.get(step_name, {}), dotted_path)


def _resolve_templates(obj: Any, context: dict[str, Any]) -> Any:
    """Recursively resolve ``{{ steps.x.y.z }}`` and ``{{ env.KEY }}`` expressions."""
    if isinstance(obj, str):
        env: dict[str, str] = context.get("env", {})

        # If the entire string is a single {{ env.KEY }} → preserve type
        env_full = _ENV_RE.fullmatch(obj.strip())
        if env_full:
            return env.get(env_full.group(1), obj)

        # If the entire string is a single {{ steps.X.Y }} → preserve type
        steps_full = _TEMPLATE_RE.fullmatch(obj.strip())
        if steps_full:
            return _resolve_ref(context, steps_full.group(1), steps_full.group(2))

        # Partial / mixed replacement — always yields a string
        def _env_replacer(m: re.Match) -> str:
            return env.get(m.group(1), m.group(0))

        def _steps_replacer(m: re.Match) -> str:
            val = _resolve_ref(context, m.group(1), m.group(2))
            if val is None:
                return m.group(0)
            if isinstance(val, (dict, list)):
                return json.dumps(val)
            return str(val)

        result = _ENV_RE.sub(_env_replacer, obj)
        result = _TEMPLATE_RE.sub(_steps_replacer, result)
        return result

    if isinstance(obj, dict):
        return {k: _resolve_templates(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_templates(item, context) for item in obj]
    return obj


# ── Defaults merging ───────────────────────────────────────────────


def _apply_defaults(step: StepDefinition, defaults: dict[str, dict[str, Any]]) -> StepDefinition:
    """Return a copy of *step* with type-level defaults deep-merged under its config.

    Step-level config takes precedence over defaults.
    """
    type_defaults = defaults.get(step.type)
    if not type_defaults:
        return step
    merged_config = deep_merge(type_defaults, step.config)
    return step.model_copy(update={"config": merged_config})


# ── Step execution ─────────────────────────────────────────────────


async def _run_step(
    step: StepDefinition,
    context: dict[str, Any],
    defaults: dict[str, dict[str, Any]] | None = None,
) -> StepResult:
    """Execute a single step with retry logic."""
    if defaults:
        step = _apply_defaults(step, defaults)
    plugin = get_plugin(step.type)
    last_result: StepResult | None = None

    for attempt in range(1, step.retry.attempts + 1):
        resolved = step.model_copy(
            update={"config": _resolve_templates(step.config, context)}
        )
        logger.info("Step '%s' — attempt %d/%d", step.name, attempt, step.retry.attempts)

        result = await plugin.execute(resolved, context)
        result.attempts = attempt
        last_result = result

        if result.status == StepStatus.SUCCESS:
            return result

        if attempt < step.retry.attempts:
            logger.warning(
                "Step '%s' failed (attempt %d), retrying in %.1fs …",
                step.name,
                attempt,
                step.retry.delay_seconds,
            )
            await asyncio.sleep(step.retry.delay_seconds)

    return last_result  # type: ignore[return-value]


# ── Dry-run ───────────────────────────────────────────────────────


_UNRESOLVED_RE = re.compile(r"\{\{.*?\}\}")


def _find_unresolved(obj: Any) -> list[str]:
    """Collect any remaining ``{{ … }}`` expressions in a resolved config tree."""
    found: list[str] = []
    if isinstance(obj, str):
        found.extend(m.group() for m in _UNRESOLVED_RE.finditer(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_find_unresolved(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_unresolved(item))
    return found


def _dry_run_workflow(workflow: WorkflowDefinition) -> None:
    """Display what each step would execute without running anything."""
    import click

    include_index = {r.step_index: r for r in workflow.include_meta}

    context: dict[str, Any] = {"env": workflow.env}
    click.echo(f"\nDry-run: {workflow.name} ({len(workflow.steps)} steps)\n")

    total_warnings = 0
    for idx, step in enumerate(workflow.steps):
        defaults_applied: list[str] = []
        if workflow.defaults:
            type_defaults = workflow.defaults.get(step.type)
            if type_defaults:
                defaults_applied = list(type_defaults.keys())
            step = _apply_defaults(step, workflow.defaults)
        resolved_config = _resolve_templates(step.config, context)

        # Step header
        header = f"  [{idx + 1}/{len(workflow.steps)}] {step.name}  ({step.type})"
        inc = include_index.get(idx)
        if inc:
            header += f"  ← {inc.include_path}"
        click.echo(header)

        click.echo(f"      config : {json.dumps(resolved_config, indent=14)}")
        if defaults_applied:
            click.echo(f"      defaults: {', '.join(defaults_applied)}")
        if step.retry.attempts > 1:
            click.echo(f"      retry  : {step.retry.attempts} attempts, {step.retry.delay_seconds}s delay")
        click.echo(f"      on_failure: {step.on_failure.value}")

        unresolved = _find_unresolved(resolved_config)
        if unresolved:
            total_warnings += len(unresolved)
            for expr in unresolved:
                click.echo(f"      ⚠ unresolved: {expr}", err=True)

        click.echo()
        context[step.name] = {"status_code": 200, "body": {}, "stdout": "", "stderr": "", "exit_code": 0}

    click.echo("No steps were executed (dry-run).")
    if total_warnings:
        click.echo(f"  {total_warnings} unresolved template(s) — check env vars and step references.")


# ── Workflow execution ─────────────────────────────────────────────


async def run_workflow(workflow: WorkflowDefinition, dry_run: bool = False) -> WorkflowResult:
    """Execute all steps in *workflow* sequentially, passing context forward."""
    if dry_run:
        _dry_run_workflow(workflow)
        return WorkflowResult(
            workflow_name=workflow.name,
            status=WorkflowStatus.SUCCESS,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

    # Ensure built-in plugins are registered
    import orchestrio.plugins  # noqa: F401

    result = WorkflowResult(
        workflow_name=workflow.name,
        status=WorkflowStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    # Shared context: each completed step stores its output under its name
    context: dict[str, Any] = {"env": workflow.env}

    logger.info("▶ Workflow '%s' [run %s]", workflow.name, result.run_id)

    all_passed = True
    for idx, step in enumerate(workflow.steps):
        logger.info("── Step %d/%d: %s (%s)", idx + 1, len(workflow.steps), step.name, step.type)

        step_result = await _run_step(step, context, defaults=workflow.defaults)
        result.steps.append(step_result)

        # Store output for downstream template resolution
        context[step.name] = step_result.output

        if step_result.status == StepStatus.SUCCESS:
            logger.info("   ✓ %s", step.name)
        else:
            logger.error("   ✗ %s — %s", step.name, step_result.error)
            all_passed = False
            if step.on_failure == OnFailure.STOP:
                for remaining in workflow.steps[idx + 1 :]:
                    result.steps.append(
                        StepResult(name=remaining.name, status=StepStatus.SKIPPED)
                    )
                break

    result.finished_at = datetime.now(timezone.utc)
    result.status = WorkflowStatus.SUCCESS if all_passed else WorkflowStatus.FAILED
    logger.info("■ Workflow '%s' → %s", workflow.name, result.status.value)
    return result
