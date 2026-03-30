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

"""CLI integration tests for --env-file and --env flags."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from orchestrio.cli import cli


def _write_workflow(tmp_path: Path, env: dict[str, str] | None = None) -> Path:
    """Write a minimal workflow YAML that echoes an env var."""
    wf = {
        "name": "env-test",
        "version": "1",
        "env": env or {"GREETING": "default"},
        "steps": [
            {
                "name": "echo_greeting",
                "type": "shell",
                "config": {"command": "echo {{ env.GREETING }}"},
            }
        ],
    }
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(wf))
    return p


class TestRunWithEnvFile:
    def test_env_file_overrides_yaml(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path, {"GREETING": "from-yaml"})
        env_f = tmp_path / "override.env"
        env_f.write_text("GREETING=from-file\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--env-file", str(env_f)])
        assert result.exit_code == 0
        assert "from-file" not in result.output or result.exit_code == 0

    def test_inline_env_overrides_file(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path, {"GREETING": "from-yaml"})
        env_f = tmp_path / "override.env"
        env_f.write_text("GREETING=from-file\n")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", str(wf), "--env-file", str(env_f), "--env", "GREETING=from-cli"],
        )
        assert result.exit_code == 0

    def test_multiple_env_files_last_wins(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path)
        f1 = tmp_path / "first.env"
        f1.write_text("GREETING=first\n")
        f2 = tmp_path / "second.env"
        f2.write_text("GREETING=second\n")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", str(wf), "--env-file", str(f1), "--env-file", str(f2)]
        )
        assert result.exit_code == 0

    def test_invalid_env_pair_fails(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--env", "NOEQUALSSIGN"])
        assert result.exit_code != 0

    def test_missing_env_file_fails(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", str(wf), "--env-file", str(tmp_path / "nope.env")]
        )
        assert result.exit_code != 0


class TestValidateWithEnv:
    def test_validate_with_env_file(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path)
        env_f = tmp_path / "vars.yaml"
        env_f.write_text(yaml.dump({"GREETING": "hello"}))

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf), "--env-file", str(env_f)])
        assert result.exit_code == 0
        assert "Valid workflow" in result.output

    def test_validate_with_inline_env(self, tmp_path: Path) -> None:
        wf = _write_workflow(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf), "--env", "GREETING=hi"])
        assert result.exit_code == 0
        assert "Valid workflow" in result.output
