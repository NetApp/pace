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

"""Tests for the step-at-a-time interactive mode (Chunk 3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.engine import run_workflow
from orchestrio.models import StepResult, StepStatus, WorkflowDefinition


# ── Helpers ────────────────────────────────────────────────────────


def _shell_wf(tmp_path: Path, num_steps: int = 3) -> Path:
    """Write a workflow with N shell steps that echo their name."""
    steps = "\n".join(
        f"  - name: step_{i}\n    type: shell\n    config:\n      command: echo step_{i}"
        for i in range(1, num_steps + 1)
    )
    wf = tmp_path / "wf.yaml"
    wf.write_text(f"name: interactive_test\nsteps:\n{steps}\n")
    return wf


def _mock_shell_result(name: str, success: bool = True) -> StepResult:
    return StepResult(
        name=name,
        status=StepStatus.SUCCESS if success else StepStatus.FAILED,
        output={"exit_code": 0 if success else 1, "stdout": f"out:{name}", "stderr": ""},
        error=None if success else "Exit code 1",
    )


def _make_workflow(steps_data: list[dict]) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test_wf",
        steps=[
            {"name": s["name"], "type": s.get("type", "shell"), "config": s.get("config", {})}
            for s in steps_data
        ],
    )


# ── CLI: --interactive flag ────────────────────────────────────────


class TestInteractiveCLIFlag:
    def test_mutually_exclusive_with_dry_run(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 1)
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--dry-run", "--interactive"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_continue_all_steps(self, tmp_path: Path):
        """Pressing Enter (default=c) at each prompt continues through all steps."""
        wf = _shell_wf(tmp_path, 2)
        runner = CliRunner()
        # Two prompts: after step_1 and after step_2 (last step, no next preview)
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="c\nc\n")
        assert result.exit_code == 0
        assert "step_1 → success" in result.output
        assert "step_2 → success" in result.output

    def test_abort_stops_workflow(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 3)
        runner = CliRunner()
        # Continue step_1, then abort after step_2
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="c\na\n")
        assert result.exit_code == 0
        assert "step_1 → success" in result.output
        assert "step_2 → success" in result.output
        assert "success" in result.output

    def test_skip_next_step(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 3)
        runner = CliRunner()
        # After step_1, skip step_2, then continue step_3
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="s\nc\n")
        assert result.exit_code == 0
        output = result.output
        assert "step_1 → success" in output
        assert "step_3 → success" in output

    def test_inspect_then_continue(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 1)
        runner = CliRunner()
        # Inspect after step_1, then continue
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="i\nc\n")
        assert result.exit_code == 0
        assert "inspect: step_1" in result.output
        assert '"stdout": "step_1"' in result.output


# ── Engine: interactive parameter ──────────────────────────────────


class TestEngineInteractive:
    async def test_continue_runs_all(self):
        wf = _make_workflow(
            [
                {"name": "a", "config": {"command": "echo a"}},
                {"name": "b", "config": {"command": "echo b"}},
            ]
        )
        with (
            patch("orchestrio.engine.get_plugin") as mock_gp,
            patch("orchestrio.engine._interactive_prompt", return_value="c"),
            patch("orchestrio.engine._print_step_summary"),
            patch("orchestrio.engine._print_next_step_preview"),
        ):
            mock_plugin = AsyncMock()
            mock_plugin.execute.side_effect = [
                _mock_shell_result("a"),
                _mock_shell_result("b"),
            ]
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=True)

        assert result.status.value == "success"
        assert len(result.steps) == 2
        assert all(s.status == StepStatus.SUCCESS for s in result.steps)

    async def test_abort_skips_remaining(self):
        wf = _make_workflow(
            [
                {"name": "a", "config": {"command": "echo a"}},
                {"name": "b", "config": {"command": "echo b"}},
                {"name": "c", "config": {"command": "echo c"}},
            ]
        )
        with (
            patch("orchestrio.engine.get_plugin") as mock_gp,
            patch("orchestrio.engine._interactive_prompt", side_effect=["c", "a"]),
            patch("orchestrio.engine._print_step_summary"),
            patch("orchestrio.engine._print_next_step_preview"),
        ):
            mock_plugin = AsyncMock()
            mock_plugin.execute.side_effect = [
                _mock_shell_result("a"),
                _mock_shell_result("b"),
            ]
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=True)

        assert len(result.steps) == 3
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[1].status == StepStatus.SUCCESS
        assert result.steps[2].status == StepStatus.SKIPPED

    async def test_skip_skips_next_step(self):
        wf = _make_workflow(
            [
                {"name": "a", "config": {"command": "echo a"}},
                {"name": "b", "config": {"command": "echo b"}},
                {"name": "c", "config": {"command": "echo c"}},
            ]
        )
        with (
            patch("orchestrio.engine.get_plugin") as mock_gp,
            patch("orchestrio.engine._interactive_prompt", side_effect=["s", "c"]),
            patch("orchestrio.engine._print_step_summary"),
            patch("orchestrio.engine._print_next_step_preview"),
        ):
            mock_plugin = AsyncMock()
            mock_plugin.execute.side_effect = [
                _mock_shell_result("a"),
                _mock_shell_result("c"),
            ]
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=True)

        assert len(result.steps) == 3
        assert result.steps[0].name == "a"
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[1].name == "b"
        assert result.steps[1].status == StepStatus.SKIPPED
        assert result.steps[2].name == "c"
        assert result.steps[2].status == StepStatus.SUCCESS

    async def test_retry_reruns_step(self):
        wf = _make_workflow(
            [
                {"name": "a", "config": {"command": "echo a"}},
            ]
        )
        with (
            patch("orchestrio.engine.get_plugin") as mock_gp,
            patch("orchestrio.engine._interactive_prompt", side_effect=["r", "c"]),
            patch("orchestrio.engine._print_step_summary"),
            patch("orchestrio.engine._print_next_step_preview"),
        ):
            mock_plugin = AsyncMock()
            # First run fails, retry succeeds
            mock_plugin.execute.side_effect = [
                _mock_shell_result("a", success=False),
                _mock_shell_result("a", success=True),
            ]
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=True)

        assert mock_plugin.execute.call_count == 2
        assert result.status.value == "success"
        assert len(result.steps) == 1
        assert result.steps[0].status == StepStatus.SUCCESS

    async def test_inspect_loops_back_to_prompt(self):
        wf = _make_workflow([{"name": "a", "config": {"command": "echo a"}}])
        with (
            patch("orchestrio.engine.get_plugin") as mock_gp,
            patch("orchestrio.engine._interactive_prompt", side_effect=["i", "c"]) as mock_prompt,
            patch("orchestrio.engine._print_step_summary"),
            patch("orchestrio.engine._print_next_step_preview"),
            patch("orchestrio.engine._inspect_step") as mock_inspect,
        ):
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = _mock_shell_result("a")
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=True)

        mock_inspect.assert_called_once()
        assert mock_prompt.call_count == 2
        assert result.status.value == "success"

    async def test_non_interactive_unchanged(self):
        """Default (interactive=False) works as before with no prompts."""
        wf = _make_workflow([{"name": "a", "config": {"command": "echo a"}}])
        with patch("orchestrio.engine.get_plugin") as mock_gp:
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = _mock_shell_result("a")
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf, interactive=False)

        assert result.status.value == "success"
        assert len(result.steps) == 1


# ── Next-step preview ──────────────────────────────────────────────


class TestNextStepPreview:
    def test_shows_next_step_config(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 2)
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="c\nc\n")
        assert result.exit_code == 0
        assert "Next:" in result.output
        assert "step_2" in result.output

    def test_no_preview_on_last_step(self, tmp_path: Path):
        wf = _shell_wf(tmp_path, 1)
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--interactive", "--no-log"], input="c\n")
        assert result.exit_code == 0
        assert "Next:" not in result.output
