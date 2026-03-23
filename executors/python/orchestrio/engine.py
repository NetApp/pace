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

logger = logging.getLogger("orchestrio.engine")

# ── Template resolution ────────────────────────────────────────────

# Matches {{ steps.stepName.field.subfield }}
_TEMPLATE_RE = re.compile(r"\{\{\s*steps\.(\w+)((?:\.\w+)+)\s*\}\}")

# Matches {{ env.VAR_NAME }}
_ENV_RE = re.compile(r"\{\{\s*env\.(\w+)\s*\}\}")


def _resolve_ref(context: dict[str, Any], step_name: str, dotted_path: str) -> Any:
    """Walk a dotted path inside a step's stored output.

    Supports both dict keys and list indices, e.g.
    ``records.0.cluster_interfaces.0.ip.address``.
    """
    value: Any = context.get(step_name, {})
    for key in dotted_path.strip(".").split("."):
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list):
            try:
                value = value[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return value


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


# ── Step execution ─────────────────────────────────────────────────


async def _run_step(step: StepDefinition, context: dict[str, Any]) -> StepResult:
    """Execute a single step with retry logic."""
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


def _dry_run_workflow(workflow: WorkflowDefinition) -> None:
    """Print what each step would execute without running anything."""
    import json

    context: dict[str, Any] = {"env": workflow.env}
    print(f"\n🔍 Dry-run: {workflow.name} ({len(workflow.steps)} steps)\n")

    for idx, step in enumerate(workflow.steps):
        resolved_config = _resolve_templates(step.config, context)
        print(f"  [{idx + 1}/{len(workflow.steps)}] {step.name}  ({step.type})")
        print(f"      config : {json.dumps(resolved_config, indent=14)}")
        if step.retry.attempts > 1:
            print(f"      retry  : {step.retry.attempts} attempts, {step.retry.delay_seconds}s delay")
        print(f"      on_failure: {step.on_failure.value}")
        print()
        # Stub output so downstream templates show their resolved form
        context[step.name] = {"status_code": 200, "body": {}, "stdout": "", "stderr": "", "exit_code": 0}

    print("⚠️  No steps were executed.")


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

        step_result = await _run_step(step, context)
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
