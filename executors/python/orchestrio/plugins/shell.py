"""Shell step plugin — executes shell commands."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from orchestrio.models import StepDefinition, StepResult, StepStatus
from orchestrio.plugins.base import StepPlugin


@StepPlugin.register("shell")
class ShellPlugin(StepPlugin):
    """Execute a shell command defined in step config.

    Expected config keys:
        command  — Shell command string
        cwd      — Optional working directory
        timeout  — Seconds (default 60)
        env      — Optional extra environment variables
    """

    async def execute(
        self,
        step: StepDefinition,
        context: dict[str, Any],
    ) -> StepResult:
        cfg = step.config
        command = cfg.get("command", "")
        cwd = cfg.get("cwd")
        timeout = cfg.get("timeout", 60)
        env_vars = cfg.get("env")

        started = datetime.now(timezone.utc)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env_vars,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            success = proc.returncode == 0
            return StepResult(
                name=step.name,
                status=StepStatus.SUCCESS if success else StepStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                output={
                    "exit_code": proc.returncode,
                    "stdout": stdout.decode().strip(),
                    "stderr": stderr.decode().strip(),
                },
                error=None if success else f"Exit code {proc.returncode}",
            )
        except asyncio.TimeoutError:
            return StepResult(
                name=step.name,
                status=StepStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=f"Command timed out after {timeout}s",
            )
        except Exception as exc:
            return StepResult(
                name=step.name,
                status=StepStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=str(exc),
            )
