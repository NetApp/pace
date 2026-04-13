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

"""Tests for the structured JSONL run logger and engine integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.engine import run_workflow
from orchestrio.models import StepResult, StepStatus, WorkflowDefinition
from orchestrio.run_logger import NullRunLogger, RunLogger, _redact


# ── _redact ────────────────────────────────────────────────────────


class TestRedact:
    def test_redacts_password(self):
        data = {"username": "admin", "password": "s3cret"}
        assert _redact(data) == {"username": "admin", "password": "***"}

    def test_redacts_authorization_header(self):
        data = {"headers": {"Authorization": "Basic abc123", "Accept": "application/json"}}
        result = _redact(data)
        assert result["headers"]["Authorization"] == "***"
        assert result["headers"]["Accept"] == "application/json"

    def test_redacts_nested_token(self):
        data = {"auth": {"token": "xyz", "user": "me"}}
        result = _redact(data)
        assert result["auth"]["token"] == "***"
        assert result["auth"]["user"] == "me"

    def test_redacts_secret_key(self):
        data = {"secret": "top_secret", "name": "wf1"}
        assert _redact(data) == {"secret": "***", "name": "wf1"}

    def test_case_insensitive(self):
        data = {"Password": "hidden", "TOKEN": "hidden2"}
        result = _redact(data)
        assert result["Password"] == "***"
        assert result["TOKEN"] == "***"

    def test_redacts_in_lists(self):
        data = [{"password": "a"}, {"password": "b"}]
        result = _redact(data)
        assert result == [{"password": "***"}, {"password": "***"}]

    def test_leaves_scalars_alone(self):
        assert _redact("hello") == "hello"
        assert _redact(42) == 42
        assert _redact(None) is None

    def test_does_not_mutate_original(self):
        data = {"password": "secret", "nested": {"token": "abc"}}
        _redact(data)
        assert data["password"] == "secret"
        assert data["nested"]["token"] == "abc"


# ── RunLogger file I/O ─────────────────────────────────────────────


class TestRunLoggerIO:
    def test_writes_jsonl_lines(self, tmp_path: Path):
        log_path = tmp_path / "test.log.jsonl"
        with RunLogger(log_path, "run123") as rlog:
            rlog.event("workflow_start", name="wf1")
            rlog.event("step_start", step="s1", step_index=0)

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

        e1 = json.loads(lines[0])
        assert e1["event"] == "workflow_start"
        assert e1["run_id"] == "run123"
        assert e1["name"] == "wf1"
        assert "ts" in e1

        e2 = json.loads(lines[1])
        assert e2["event"] == "step_start"
        assert e2["step"] == "s1"

    def test_redacts_sensitive_payload(self, tmp_path: Path):
        log_path = tmp_path / "redact.log.jsonl"
        with RunLogger(log_path, "r1") as rlog:
            rlog.event("step_attempt", config={"password": "s3cret", "url": "http://x"})

        line = json.loads(log_path.read_text().strip())
        assert line["config"]["password"] == "***"
        assert line["config"]["url"] == "http://x"

    def test_path_property(self, tmp_path: Path):
        log_path = tmp_path / "p.jsonl"
        rlog = RunLogger(log_path, "r1")
        assert rlog.path == log_path

    def test_no_write_after_close(self, tmp_path: Path):
        log_path = tmp_path / "closed.jsonl"
        rlog = RunLogger(log_path, "r1")
        rlog.__enter__()
        rlog.event("first")
        rlog.close()
        rlog.event("second")
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_append_mode(self, tmp_path: Path):
        log_path = tmp_path / "append.jsonl"
        log_path.write_text('{"existing": true}\n')
        with RunLogger(log_path, "r1") as rlog:
            rlog.event("new_event")
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"existing": True}


# ── NullRunLogger ──────────────────────────────────────────────────


class TestNullRunLogger:
    def test_no_file_created(self, tmp_path: Path):
        with NullRunLogger() as rlog:
            rlog.event("workflow_start", name="wf1")
        assert not (tmp_path / "any.jsonl").exists()

    def test_context_manager(self):
        with NullRunLogger() as rlog:
            rlog.event("anything", x=1)


# ── Engine integration ─────────────────────────────────────────────


def _make_workflow(steps_data: list[dict]) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test_wf",
        steps=[
            {"name": s["name"], "type": s.get("type", "shell"), "config": s.get("config", {})}
            for s in steps_data
        ],
    )


def _mock_shell_result(name: str, success: bool = True) -> StepResult:
    return StepResult(
        name=name,
        status=StepStatus.SUCCESS if success else StepStatus.FAILED,
        output={"exit_code": 0 if success else 1, "stdout": "ok", "stderr": ""},
        error=None if success else "Exit code 1",
    )


class TestEngineLogging:
    async def test_workflow_events_logged(self, tmp_path: Path):
        wf = _make_workflow(
            [
                {"name": "step_a", "config": {"command": "echo a"}},
            ]
        )
        log_path = tmp_path / "run.log.jsonl"

        mock_result = _mock_shell_result("step_a")
        with patch("orchestrio.engine.get_plugin") as mock_gp:
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = mock_result
            mock_gp.return_value = mock_plugin

            with RunLogger(log_path, "test_run") as rlog:
                result = await run_workflow(wf, run_log=rlog)

        assert result.status.value == "success"
        assert result.log_file == str(log_path)

        lines = [json.loads(ln) for ln in log_path.read_text().strip().split("\n")]
        events = [ln["event"] for ln in lines]
        assert events == [
            "workflow_start",
            "step_start",
            "step_attempt",
            "step_success",
            "workflow_end",
        ]

        assert lines[0]["workflow"] == "test_wf"
        assert lines[0]["total_steps"] == 1
        assert lines[-1]["status"] == "success"
        assert lines[-1]["passed"] == 1

    async def test_failed_step_events(self, tmp_path: Path):
        wf = _make_workflow(
            [
                {"name": "fail_step", "config": {"command": "false"}},
                {"name": "skip_step", "config": {"command": "echo ok"}},
            ]
        )
        log_path = tmp_path / "fail.log.jsonl"

        with patch("orchestrio.engine.get_plugin") as mock_gp:
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = _mock_shell_result("fail_step", success=False)
            mock_gp.return_value = mock_plugin

            with RunLogger(log_path, "fail_run") as rlog:
                result = await run_workflow(wf, run_log=rlog)

        assert result.status.value == "failed"
        lines = [json.loads(ln) for ln in log_path.read_text().strip().split("\n")]
        events = [ln["event"] for ln in lines]
        assert "step_failed" in events
        assert "step_skipped" in events
        assert "workflow_end" in events

        skip_event = next(ln for ln in lines if ln["event"] == "step_skipped")
        assert skip_event["step"] == "skip_step"
        assert "fail_step" in skip_event["reason"]

        end_event = next(ln for ln in lines if ln["event"] == "workflow_end")
        assert end_event["failed"] == 1
        assert end_event["skipped"] == 1

    async def test_null_logger_no_log_file(self):
        wf = _make_workflow([{"name": "s1", "config": {"command": "echo x"}}])
        with patch("orchestrio.engine.get_plugin") as mock_gp:
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = _mock_shell_result("s1")
            mock_gp.return_value = mock_plugin

            result = await run_workflow(wf)

        assert result.log_file is None

    async def test_redaction_in_log_events(self, tmp_path: Path):
        wf = WorkflowDefinition(
            name="redact_wf",
            defaults={"http": {"password": "s3cret"}},
            steps=[
                {
                    "name": "api_call",
                    "type": "http",
                    "config": {
                        "url": "http://host/api",
                        "password": "s3cret",
                    },
                }
            ],
        )
        log_path = tmp_path / "redact.log.jsonl"

        with patch("orchestrio.engine.get_plugin") as mock_gp:
            mock_plugin = AsyncMock()
            mock_plugin.execute.return_value = StepResult(
                name="api_call",
                status=StepStatus.SUCCESS,
                output={"status_code": 200, "body": {}},
            )
            mock_gp.return_value = mock_plugin

            with RunLogger(log_path, "r1") as rlog:
                await run_workflow(wf, run_log=rlog)

        lines = [json.loads(ln) for ln in log_path.read_text().strip().split("\n")]
        attempt_event = next(ln for ln in lines if ln["event"] == "step_attempt")
        assert attempt_event["config"]["password"] == "***"


# ── CLI integration ────────────────────────────────────────────────


class TestCLILogging:
    def test_log_file_created(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: cli_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )
        log_path = tmp_path / "out.log.jsonl"

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--log-file", str(log_path)])
        assert result.exit_code == 0
        assert log_path.exists()

        lines = [json.loads(ln) for ln in log_path.read_text().strip().split("\n")]
        events = [ln["event"] for ln in lines]
        assert "workflow_start" in events
        assert "workflow_end" in events

    def test_no_log_flag(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: nolog_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--no-log"])
        assert result.exit_code == 0
        assert "Log" not in result.output or "Log" in result.output

    def test_no_log_flag_json(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: nolog_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--no-log", "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["log_file"] is None

    def test_log_file_in_result_json(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: res_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )
        log_path = tmp_path / "result.log.jsonl"

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--log-file", str(log_path), "--json"])
        assert result.exit_code == 0
        json_start = result.output.index("{")
        output = json.loads(result.output[json_start:])
        assert output["log_file"] == str(log_path)

    def test_human_summary_by_default(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: summary_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--no-log"])
        assert result.exit_code == 0
        assert "summary_test" in result.output
        assert "success" in result.output
        assert "1 passed" in result.output

    def test_default_log_file_auto_generated(self, tmp_path: Path, monkeypatch):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: auto_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file)])
        assert result.exit_code == 0
        assert "Log written to logs/" in result.output
        logs_dir = tmp_path / "logs"
        assert logs_dir.is_dir()
        log_files = list(logs_dir.glob("run-*.log.jsonl"))
        assert len(log_files) == 1

    def test_dry_run_no_log_file(self, tmp_path: Path):
        wf_file = tmp_path / "wf.yaml"
        wf_file.write_text(
            "name: dry_test\n"
            "steps:\n"
            "  - name: hello\n"
            "    type: shell\n"
            "    config:\n"
            "      command: echo hi\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_file), "--dry-run"])
        assert result.exit_code == 0
        assert "log_file" not in result.output
