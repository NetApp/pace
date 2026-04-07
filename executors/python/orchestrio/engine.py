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
from orchestrio.run_logger import NullRunLogger, RunLogger
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
    run_log: RunLogger | NullRunLogger | None = None,
    step_index: int = 0,
    total_steps: int = 1,
) -> StepResult:
    """Execute a single step with retry logic."""
    if run_log is None:
        run_log = NullRunLogger()
    if defaults:
        step = _apply_defaults(step, defaults)
    plugin = get_plugin(step.type)
    last_result: StepResult | None = None

    run_log.event(
        "step_start",
        step=step.name,
        step_index=step_index,
        step_type=step.type,
        position=f"{step_index + 1}/{total_steps}",
        max_attempts=step.retry.attempts,
    )

    for attempt in range(1, step.retry.attempts + 1):
        resolved = step.model_copy(
            update={"config": _resolve_templates(step.config, context)}
        )
        logger.info("Step '%s' — attempt %d/%d", step.name, attempt, step.retry.attempts)

        run_log.event(
            "step_attempt",
            step=step.name,
            attempt=attempt,
            max_attempts=step.retry.attempts,
            config=resolved.config,
        )

        result = await plugin.execute(resolved, context)
        result.attempts = attempt
        last_result = result

        if result.status == StepStatus.SUCCESS:
            run_log.event(
                "step_success",
                step=step.name,
                attempt=attempt,
                output=result.output,
                duration_ms=_duration_ms(result),
            )
            return result

        run_log.event(
            "step_failed",
            step=step.name,
            attempt=attempt,
            error=result.error,
            output=result.output,
            duration_ms=_duration_ms(result),
        )

        if attempt < step.retry.attempts:
            logger.warning(
                "Step '%s' failed (attempt %d), retrying in %.1fs …",
                step.name,
                attempt,
                step.retry.delay_seconds,
            )
            await asyncio.sleep(step.retry.delay_seconds)

    return last_result  # type: ignore[return-value]


def _duration_ms(result: StepResult) -> float | None:
    if result.started_at and result.finished_at:
        return round((result.finished_at - result.started_at).total_seconds() * 1000, 1)
    return None


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


def _collect_step_refs(obj: Any) -> set[str]:
    """Return the set of step names referenced via ``{{ steps.NAME.… }}``."""
    refs: set[str] = set()
    if isinstance(obj, str):
        refs.update(m.group(1) for m in _TEMPLATE_RE.finditer(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            refs.update(_collect_step_refs(v))
    elif isinstance(obj, list):
        for item in obj:
            refs.update(_collect_step_refs(item))
    return refs


def _collect_env_refs(obj: Any) -> set[str]:
    """Return the set of env var names referenced via ``{{ env.NAME }}``."""
    refs: set[str] = set()
    if isinstance(obj, str):
        refs.update(m.group(1) for m in _ENV_RE.finditer(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            refs.update(_collect_env_refs(v))
    elif isinstance(obj, list):
        for item in obj:
            refs.update(_collect_env_refs(item))
    return refs


_CONFIG_REQUIRED_KEYS: dict[str, list[str]] = {
    "http": ["url"],
    "shell": ["command"],
}


def _dry_run_workflow(workflow: WorkflowDefinition) -> None:
    """Display what each step would execute without running anything."""
    import click

    include_index = {r.step_index: r for r in workflow.include_meta}
    step_names = [s.name for s in workflow.steps]
    step_name_set = set(step_names)

    context: dict[str, Any] = {"env": workflow.env}
    click.echo(f"\nDry-run: {workflow.name} ({len(workflow.steps)} steps)\n")

    total_warnings = 0
    all_env_refs: set[str] = set()
    dep_graph: dict[str, set[str]] = {}

    for idx, step in enumerate(workflow.steps):
        defaults_applied: list[str] = []
        if workflow.defaults:
            type_defaults = workflow.defaults.get(step.type)
            if type_defaults:
                defaults_applied = list(type_defaults.keys())
            step = _apply_defaults(step, workflow.defaults)

        # Collect references before resolution
        step_refs = _collect_step_refs(step.config)
        env_refs = _collect_env_refs(step.config)
        if workflow.defaults and step.type in workflow.defaults:
            env_refs.update(_collect_env_refs(workflow.defaults[step.type]))
        all_env_refs.update(env_refs)
        dep_graph[step.name] = step_refs

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
        if step_refs:
            click.echo(f"      depends : {', '.join(sorted(step_refs))}")
        if step.retry.attempts > 1:
            click.echo(f"      retry  : {step.retry.attempts} attempts, {step.retry.delay_seconds}s delay")
        click.echo(f"      on_failure: {step.on_failure.value}")

        # Dependency warnings
        prior_names = set(step_names[:idx])
        for ref in sorted(step_refs):
            if ref not in step_name_set:
                total_warnings += 1
                click.echo(f"      ⚠ references unknown step '{ref}'", err=True)
            elif ref not in prior_names:
                total_warnings += 1
                click.echo(
                    f"      ⚠ forward reference to '{ref}' (defined later at step "
                    f"{step_names.index(ref) + 1})",
                    err=True,
                )

        # Config schema hints
        required_keys = _CONFIG_REQUIRED_KEYS.get(step.type, [])
        for key in required_keys:
            val = resolved_config.get(key)
            if not val or (isinstance(val, str) and not val.strip()):
                total_warnings += 1
                click.echo(
                    f"      ⚠ '{key}' is missing or empty for {step.type} step",
                    err=True,
                )

        unresolved = _find_unresolved(resolved_config)
        if unresolved:
            total_warnings += len(unresolved)
            for expr in unresolved:
                click.echo(f"      ⚠ unresolved: {expr}", err=True)

        click.echo()
        context[step.name] = {"status_code": 200, "body": {}, "stdout": "", "stderr": "", "exit_code": 0}

    # ── Summary ────────────────────────────────────────────────────

    # Env completeness
    missing_env = sorted(all_env_refs - set(workflow.env.keys()))
    if missing_env:
        total_warnings += len(missing_env)
        click.echo("  Missing env vars:")
        for var in missing_env:
            click.echo(f"    ⚠ {{ env.{var} }} — not provided", err=True)
        click.echo()

    # Dependency summary
    has_deps = {name: refs for name, refs in dep_graph.items() if refs}
    if has_deps:
        click.echo("  Step dependencies:")
        for name, refs in has_deps.items():
            click.echo(f"    {name} → {', '.join(sorted(refs))}")
        click.echo()

    click.echo("No steps were executed (dry-run).")
    if total_warnings:
        click.echo(f"  {total_warnings} warning(s) — review before running.")


# ── Interactive prompt ──────────────────────────────────────────────


def _print_step_summary(step_result: StepResult) -> None:
    """Print a compact result summary for a just-completed step."""
    import click

    status_icon = "✓" if step_result.status == StepStatus.SUCCESS else "✗"
    duration = _duration_ms(step_result)
    dur_str = f" ({duration:.0f}ms)" if duration else ""

    click.echo(f"\n  {status_icon} {step_result.name} → {step_result.status.value}{dur_str}")
    if step_result.error:
        click.echo(f"    error: {step_result.error}")

    output = step_result.output
    if output.get("status_code"):
        click.echo(f"    status_code: {output['status_code']}")
    if output.get("stdout"):
        stdout_preview = output["stdout"][:120]
        click.echo(f"    stdout: {stdout_preview}")
    if output.get("stderr"):
        stderr_preview = output["stderr"][:120]
        click.echo(f"    stderr: {stderr_preview}")


def _print_next_step_preview(
    step: StepDefinition,
    context: dict[str, Any],
    defaults: dict[str, dict[str, Any]],
    idx: int,
    total: int,
) -> None:
    """Show resolved config of the upcoming step."""
    import click

    effective = _apply_defaults(step, defaults) if defaults else step
    resolved_config = _resolve_templates(effective.config, context)
    click.echo(f"\n  Next: [{idx + 1}/{total}] {step.name}  ({step.type})")
    click.echo(f"    config: {json.dumps(resolved_config, indent=12)}")


def _interactive_prompt() -> str:
    """Prompt the user for an interactive-mode action.

    Returns one of: 'c', 's', 'r', 'a', 'i'.
    """
    import click

    while True:
        choice = click.prompt(
            "\n  [c]ontinue / [s]kip / [r]etry / [a]bort / [i]nspect",
            type=str,
            default="c",
            show_default=False,
        ).strip().lower()
        if choice in ("c", "s", "r", "a", "i"):
            return choice
        click.echo("  Invalid choice. Enter c, s, r, a, or i.")


def _inspect_step(step_result: StepResult) -> None:
    """Dump the full step output as formatted JSON."""
    import click

    click.echo(f"\n  ── inspect: {step_result.name} ──")
    click.echo(json.dumps(step_result.output, indent=2, default=str))


# ── Workflow execution ─────────────────────────────────────────────


async def run_workflow(
    workflow: WorkflowDefinition,
    dry_run: bool = False,
    run_log: RunLogger | NullRunLogger | None = None,
    interactive: bool = False,
) -> WorkflowResult:
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

    if run_log is None:
        run_log = NullRunLogger()

    run_log.event(
        "workflow_start",
        workflow=workflow.name,
        total_steps=len(workflow.steps),
        step_names=[s.name for s in workflow.steps],
    )

    # Shared context: each completed step stores its output under its name
    context: dict[str, Any] = {"env": workflow.env}

    logger.info("▶ Workflow '%s' [run %s]", workflow.name, result.run_id)

    all_passed = True
    idx = 0
    while idx < len(workflow.steps):
        step = workflow.steps[idx]
        logger.info("── Step %d/%d: %s (%s)", idx + 1, len(workflow.steps), step.name, step.type)

        step_result = await _run_step(
            step,
            context,
            defaults=workflow.defaults,
            run_log=run_log,
            step_index=idx,
            total_steps=len(workflow.steps),
        )

        if interactive:
            _print_step_summary(step_result)

            if idx + 1 < len(workflow.steps):
                _print_next_step_preview(
                    workflow.steps[idx + 1], context, workflow.defaults, idx + 1, len(workflow.steps)
                )

            action = _interactive_prompt()

            while action == "i":
                _inspect_step(step_result)
                action = _interactive_prompt()

            if action == "r":
                continue  # re-run same idx without advancing

            if action == "a":
                result.steps.append(step_result)
                context[step.name] = step_result.output
                for remaining in workflow.steps[idx + 1 :]:
                    skipped = StepResult(name=remaining.name, status=StepStatus.SKIPPED)
                    result.steps.append(skipped)
                    run_log.event(
                        "step_skipped", step=remaining.name, reason="aborted by user",
                    )
                all_passed = step_result.status == StepStatus.SUCCESS and all_passed
                break

            if action == "s" and idx + 1 < len(workflow.steps):
                result.steps.append(step_result)
                context[step.name] = step_result.output
                next_step = workflow.steps[idx + 1]
                skipped = StepResult(name=next_step.name, status=StepStatus.SKIPPED)
                result.steps.append(skipped)
                run_log.event(
                    "step_skipped", step=next_step.name, reason="skipped by user",
                )
                idx += 2  # skip the next step
                continue

        result.steps.append(step_result)
        context[step.name] = step_result.output

        if step_result.status == StepStatus.SUCCESS:
            logger.info("   ✓ %s", step.name)
        else:
            logger.error("   ✗ %s — %s", step.name, step_result.error)
            all_passed = False
            if step.on_failure == OnFailure.STOP:
                for remaining in workflow.steps[idx + 1 :]:
                    skipped = StepResult(name=remaining.name, status=StepStatus.SKIPPED)
                    result.steps.append(skipped)
                    run_log.event(
                        "step_skipped",
                        step=remaining.name,
                        reason=f"prior step '{step.name}' failed with on_failure=stop",
                    )
                break

        idx += 1

    result.finished_at = datetime.now(timezone.utc)
    result.status = WorkflowStatus.SUCCESS if all_passed else WorkflowStatus.FAILED
    result.log_file = str(run_log.path) if not isinstance(run_log, NullRunLogger) else None

    run_log.event(
        "workflow_end",
        workflow=workflow.name,
        status=result.status.value,
        total_steps=len(result.steps),
        passed=sum(1 for s in result.steps if s.status == StepStatus.SUCCESS),
        failed=sum(1 for s in result.steps if s.status == StepStatus.FAILED),
        skipped=sum(1 for s in result.steps if s.status == StepStatus.SKIPPED),
    )

    logger.info("■ Workflow '%s' → %s", workflow.name, result.status.value)
    return result
