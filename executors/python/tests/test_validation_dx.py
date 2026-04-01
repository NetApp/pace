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

"""Tests for Chunk 4: validation + DX enhancements."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.engine import _find_unresolved
from orchestrio.parser import load_workflow


# ── Helpers ────────────────────────────────────────────────────────


def _write_fragment(tmp_path: Path, filename: str, fragment: dict) -> Path:
    p = tmp_path / filename
    p.write_text(yaml.dump(fragment))
    return p


def _write_workflow(tmp_path: Path, steps: list, **extra) -> Path:
    wf = {"name": "dx-test", "version": "1", "steps": steps, **extra}
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(wf))
    return p


SHELL_FRAGMENT = {
    "name": "greet",
    "type": "shell",
    "config": {"command": "echo hello"},
}

HTTP_FRAGMENT = {
    "name": "fetch",
    "type": "http",
    "config": {"method": "GET", "url": "https://example.com"},
}


# ── include_meta on WorkflowDefinition ────────────────────────────


class TestIncludeMeta:
    def test_include_meta_populated(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        wf = load_workflow(wf_path)
        assert len(wf.include_meta) == 1
        assert wf.include_meta[0].step_name == "greet"
        assert wf.include_meta[0].include_path == "greet.yaml"
        assert wf.include_meta[0].step_index == 0

    def test_include_meta_empty_for_inline(self, tmp_path: Path) -> None:
        steps = [{"name": "s1", "type": "shell", "config": {"command": "echo"}}]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.include_meta == []

    def test_include_meta_mixed(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        steps = [
            {"name": "inline", "type": "shell", "config": {"command": "echo"}},
            {"include": "greet.yaml"},
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert len(wf.include_meta) == 1
        assert wf.include_meta[0].step_index == 1

    def test_include_meta_with_override_name(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        steps = [{"include": "greet.yaml", "override": {"name": "custom"}}]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.include_meta[0].step_name == "custom"

    def test_include_meta_excluded_from_json(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        wf = load_workflow(wf_path)
        json_data = wf.model_dump_json()
        assert "include_meta" not in json_data


# ── validate command enhancements ─────────────────────────────────


class TestValidateEnhancements:
    def test_validate_reports_includes(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "↳ Step 'greet' included from greet.yaml" in result.output

    def test_validate_no_includes_no_arrows(self, tmp_path: Path) -> None:
        steps = [{"name": "s1", "type": "shell", "config": {"command": "echo"}}]
        wf_path = _write_workflow(tmp_path, steps)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "↳" not in result.output

    def test_validate_warns_unused_defaults(self, tmp_path: Path) -> None:
        steps = [{"name": "s1", "type": "shell", "config": {"command": "echo"}}]
        wf_path = _write_workflow(
            tmp_path, steps, defaults={"http": {"timeout": 30}}
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "⚠ defaults.http" in result.output
        assert "no steps of type 'http'" in result.output

    def test_validate_no_warn_when_defaults_used(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        wf_path = _write_workflow(
            tmp_path,
            [{"include": "fetch.yaml"}],
            defaults={"http": {"timeout": 30}},
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "⚠" not in result.output

    def test_validate_multiple_includes_reported(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        wf_path = _write_workflow(
            tmp_path, [{"include": "greet.yaml"}, {"include": "fetch.yaml"}]
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "greet.yaml" in result.output
        assert "fetch.yaml" in result.output


# ── _find_unresolved unit tests ───────────────────────────────────


class TestFindUnresolved:
    def test_finds_env_refs(self) -> None:
        assert _find_unresolved("{{ env.MISSING }}") == ["{{ env.MISSING }}"]

    def test_finds_step_refs(self) -> None:
        result = _find_unresolved("prefix {{ steps.s1.body.id }} suffix")
        assert result == ["{{ steps.s1.body.id }}"]

    def test_finds_multiple(self) -> None:
        obj = {"a": "{{ env.X }}", "b": ["{{ env.Y }}", "resolved"]}
        assert len(_find_unresolved(obj)) == 2

    def test_returns_empty_when_all_resolved(self) -> None:
        assert _find_unresolved({"a": "resolved", "b": 42}) == []

    def test_handles_nested_dicts(self) -> None:
        obj = {"l1": {"l2": {"val": "{{ env.DEEP }}"}}}
        assert _find_unresolved(obj) == ["{{ env.DEEP }}"]

    def test_handles_none_and_numbers(self) -> None:
        assert _find_unresolved(None) == []
        assert _find_unresolved(42) == []
        assert _find_unresolved(True) == []


# ── dry-run enhancements ─────────────────────────────────────────


class TestDryRunEnhancements:
    def test_dry_run_shows_include_source(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SHELL_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "← greet.yaml" in result.output

    def test_dry_run_shows_defaults_keys(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        wf_path = _write_workflow(
            tmp_path,
            [{"include": "fetch.yaml"}],
            defaults={"http": {"timeout": 30, "verify_ssl": False}},
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "defaults:" in result.output
        assert "timeout" in result.output
        assert "verify_ssl" in result.output

    def test_dry_run_no_defaults_line_for_shell(self, tmp_path: Path) -> None:
        steps = [{"name": "s1", "type": "shell", "config": {"command": "echo hi"}}]
        wf_path = _write_workflow(
            tmp_path, steps, defaults={"http": {"timeout": 30}}
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "defaults:" not in result.output

    def test_dry_run_warns_unresolved_templates(self, tmp_path: Path) -> None:
        steps = [
            {
                "name": "s1",
                "type": "shell",
                "config": {"command": "echo {{ env.MISSING }}"},
            }
        ]
        wf_path = _write_workflow(tmp_path, steps, env={"OTHER": "val"})

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "⚠ unresolved:" in result.output
        assert "env.MISSING" in result.output
        assert "unresolved template(s)" in result.output

    def test_dry_run_no_warnings_when_clean(self, tmp_path: Path) -> None:
        steps = [
            {
                "name": "s1",
                "type": "shell",
                "config": {"command": "echo {{ env.GREETING }}"},
            }
        ]
        wf_path = _write_workflow(tmp_path, steps, env={"GREETING": "hello"})

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "⚠" not in result.output
        assert "unresolved" not in result.output

    def test_dry_run_inline_step_no_arrow(self, tmp_path: Path) -> None:
        steps = [{"name": "s1", "type": "shell", "config": {"command": "echo"}}]
        wf_path = _write_workflow(tmp_path, steps)

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "←" not in result.output
