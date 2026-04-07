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

"""Tests for the workflow-level ``defaults`` feature."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.engine import _apply_defaults
from orchestrio.utils import deep_merge
from orchestrio.models import StepDefinition


# ── deep_merge unit tests ─────────────────────────────────────────


class TestDeepMerge:
    def test_flat_override_wins(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        assert deep_merge(base, override) == {"a": 1, "b": 99, "c": 3}

    def test_nested_dicts_merged(self) -> None:
        base = {"headers": {"Accept": "json", "X-App": "orchestrio"}}
        override = {"headers": {"Accept": "xml"}}
        result = deep_merge(base, override)
        assert result == {"headers": {"Accept": "xml", "X-App": "orchestrio"}}

    def test_override_replaces_non_dict_with_dict(self) -> None:
        base = {"headers": "flat-string"}
        override = {"headers": {"Accept": "json"}}
        assert deep_merge(base, override) == {"headers": {"Accept": "json"}}

    def test_override_replaces_dict_with_scalar(self) -> None:
        base = {"headers": {"Accept": "json"}}
        override = {"headers": "gone"}
        assert deep_merge(base, override) == {"headers": "gone"}

    def test_empty_override_returns_base(self) -> None:
        base = {"a": 1}
        assert deep_merge(base, {}) == {"a": 1}

    def test_empty_base_returns_override(self) -> None:
        assert deep_merge({}, {"a": 1}) == {"a": 1}

    def test_deeply_nested(self) -> None:
        base = {"l1": {"l2": {"l3": "base", "keep": True}}}
        override = {"l1": {"l2": {"l3": "override"}}}
        result = deep_merge(base, override)
        assert result == {"l1": {"l2": {"l3": "override", "keep": True}}}

    def test_does_not_mutate_inputs(self) -> None:
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        deep_merge(base, override)
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}


# ── _apply_defaults unit tests ────────────────────────────────────


class TestApplyDefaults:
    def test_defaults_merge_into_step_config(self) -> None:
        step = StepDefinition(name="s1", type="http", config={"url": "https://x"})
        defaults = {"http": {"timeout": 30, "verify_ssl": False}}
        result = _apply_defaults(step, defaults)
        assert result.config == {"url": "https://x", "timeout": 30, "verify_ssl": False}

    def test_step_config_overrides_defaults(self) -> None:
        step = StepDefinition(name="s1", type="http", config={"timeout": 60})
        defaults = {"http": {"timeout": 30}}
        result = _apply_defaults(step, defaults)
        assert result.config["timeout"] == 60

    def test_nested_config_merged_not_replaced(self) -> None:
        step = StepDefinition(
            name="s1",
            type="http",
            config={"headers": {"Content-Type": "application/json"}},
        )
        defaults = {
            "http": {
                "headers": {"Accept": "application/hal+json", "X-App": "orchestrio"},
            }
        }
        result = _apply_defaults(step, defaults)
        assert result.config["headers"] == {
            "Accept": "application/hal+json",
            "X-App": "orchestrio",
            "Content-Type": "application/json",
        }

    def test_defaults_only_apply_to_matching_type(self) -> None:
        shell_step = StepDefinition(
            name="s1", type="shell", config={"command": "echo hi"}
        )
        defaults = {"http": {"timeout": 30, "verify_ssl": False}}
        result = _apply_defaults(shell_step, defaults)
        assert result.config == {"command": "echo hi"}

    def test_no_defaults_returns_original(self) -> None:
        step = StepDefinition(name="s1", type="http", config={"url": "https://x"})
        result = _apply_defaults(step, {})
        assert result.config == {"url": "https://x"}

    def test_does_not_mutate_original_step(self) -> None:
        step = StepDefinition(name="s1", type="http", config={"url": "https://x"})
        defaults = {"http": {"timeout": 30}}
        _apply_defaults(step, defaults)
        assert "timeout" not in step.config


# ── Integration: workflow with defaults via CLI ───────────────────


def _write_workflow_with_defaults(
    tmp_path: Path,
    defaults: dict | None = None,
    steps: list | None = None,
) -> Path:
    wf = {
        "name": "defaults-test",
        "version": "1",
        "env": {"GREETING": "hello"},
        "steps": steps
        or [
            {
                "name": "echo_it",
                "type": "shell",
                "config": {"command": "echo {{ env.GREETING }}"},
            }
        ],
    }
    if defaults:
        wf["defaults"] = defaults
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(wf))
    return p


class TestDefaultsCLI:
    def test_workflow_with_defaults_validates(self, tmp_path: Path) -> None:
        wf = _write_workflow_with_defaults(
            tmp_path,
            defaults={"http": {"timeout": 30, "verify_ssl": False}},
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf)])
        assert result.exit_code == 0
        assert "Valid workflow" in result.output

    def test_workflow_without_defaults_still_works(self, tmp_path: Path) -> None:
        wf = _write_workflow_with_defaults(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf)])
        assert result.exit_code == 0
        assert "Valid workflow" in result.output

    def test_run_shell_step_with_http_defaults(self, tmp_path: Path) -> None:
        """HTTP defaults must not leak into shell steps."""
        wf = _write_workflow_with_defaults(
            tmp_path,
            defaults={"http": {"timeout": 30}},
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--no-log"])
        assert result.exit_code == 0

    def test_dry_run_shows_merged_defaults(self, tmp_path: Path) -> None:
        wf = _write_workflow_with_defaults(
            tmp_path,
            defaults={"http": {"verify_ssl": False, "timeout": 99}},
            steps=[
                {
                    "name": "call_api",
                    "type": "http",
                    "config": {
                        "method": "GET",
                        "url": "https://example.com",
                    },
                }
            ],
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--dry-run"])
        assert result.exit_code == 0
        assert "verify_ssl" in result.output
        assert "99" in result.output

    def test_run_with_defaults_executes(self, tmp_path: Path) -> None:
        """End-to-end: defaults are applied to a shell step (no-op for shell type)."""
        wf = _write_workflow_with_defaults(
            tmp_path,
            defaults={"shell": {"timeout": 10}},
            steps=[
                {
                    "name": "echo_it",
                    "type": "shell",
                    "config": {"command": "echo works"},
                }
            ],
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--no-log"])
        assert result.exit_code == 0
        assert '"status": "success"' in result.output
