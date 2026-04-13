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

"""Tests for the enhanced dry-run static analysis (Chunk 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.engine import _collect_env_refs, _collect_step_refs


# ── Helpers ────────────────────────────────────────────────────────


def _write_wf(tmp_path: Path, data: dict[str, Any]) -> Path:
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(data, sort_keys=False))
    return p


def _dry_run(tmp_path: Path, data: dict[str, Any]) -> tuple[str, str, int]:
    """Write workflow, run dry-run, return (stdout, stderr, exit_code)."""
    wf = _write_wf(tmp_path, data)
    runner = CliRunner(catch_exceptions=False)
    result = runner.invoke(cli, ["run", str(wf), "--dry-run"])
    stderr = getattr(result, "stderr", "") or ""
    return result.output, stderr, result.exit_code


# ── _collect_step_refs / _collect_env_refs unit tests ──────────────


class TestCollectStepRefs:
    def test_basic_ref(self):
        assert _collect_step_refs("{{ steps.get_cluster.body.name }}") == {"get_cluster"}

    def test_multiple_refs(self):
        cfg = {
            "url": "{{ steps.discover.body.uuid }}",
            "body": {"name": "{{ steps.setup.body.name }}"},
        }
        assert _collect_step_refs(cfg) == {"discover", "setup"}

    def test_no_refs(self):
        assert _collect_step_refs({"url": "http://example.com"}) == set()

    def test_list_values(self):
        cfg = ["{{ steps.a.body.x }}", "plain", "{{ steps.b.body.y }}"]
        assert _collect_step_refs(cfg) == {"a", "b"}

    def test_non_string(self):
        assert _collect_step_refs(42) == set()
        assert _collect_step_refs(None) == set()


class TestCollectEnvRefs:
    def test_basic_ref(self):
        assert _collect_env_refs("{{ env.ONTAP_HOST }}") == {"ONTAP_HOST"}

    def test_multiple_in_string(self):
        s = "https://{{ env.HOST }}:{{ env.PORT }}/api"
        assert _collect_env_refs(s) == {"HOST", "PORT"}

    def test_nested_dict(self):
        cfg = {"auth": {"user": "{{ env.USER }}", "pass": "{{ env.PASS }}"}}
        assert _collect_env_refs(cfg) == {"USER", "PASS"}

    def test_no_refs(self):
        assert _collect_env_refs({"timeout": 30}) == set()


# ── Dependency graph warnings ──────────────────────────────────────


class TestDependencyWarnings:
    def test_forward_reference_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "fwd_ref",
                "steps": [
                    {
                        "name": "step_a",
                        "type": "shell",
                        "config": {"command": "echo {{ steps.step_b.body.x }}"},
                    },
                    {
                        "name": "step_b",
                        "type": "shell",
                        "config": {"command": "echo hello"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "forward reference to 'step_b'" in combined

    def test_unknown_step_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "bad_ref",
                "steps": [
                    {
                        "name": "step_a",
                        "type": "shell",
                        "config": {"command": "echo {{ steps.nonexistent.body.x }}"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "references unknown step 'nonexistent'" in combined

    def test_valid_backward_ref_no_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "good_ref",
                "steps": [
                    {
                        "name": "step_a",
                        "type": "shell",
                        "config": {"command": "echo hello"},
                    },
                    {
                        "name": "step_b",
                        "type": "shell",
                        "config": {"command": "echo {{ steps.step_a.stdout }}"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "forward reference" not in combined
        assert "unknown step" not in combined

    def test_depends_line_shown(self, tmp_path: Path):
        stdout, _, code = _dry_run(
            tmp_path,
            {
                "name": "dep_line",
                "steps": [
                    {"name": "s1", "type": "shell", "config": {"command": "echo a"}},
                    {
                        "name": "s2",
                        "type": "shell",
                        "config": {"command": "echo {{ steps.s1.stdout }}"},
                    },
                ],
            },
        )
        assert code == 0
        assert "depends : s1" in stdout


# ── Env completeness ──────────────────────────────────────────────


class TestEnvCompleteness:
    def test_missing_env_reported(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "missing_env",
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {
                            "url": "https://{{ env.HOST }}/api",
                            "method": "GET",
                        },
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "Missing env vars" in combined
        assert "env.HOST" in combined

    def test_provided_env_no_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "env_ok",
                "env": {"HOST": "10.0.0.1"},
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {
                            "url": "https://{{ env.HOST }}/api",
                            "method": "GET",
                        },
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "Missing env vars" not in combined

    def test_partial_env_reports_only_missing(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "partial_env",
                "env": {"HOST": "10.0.0.1"},
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {
                            "url": "https://{{ env.HOST }}/api",
                            "username": "{{ env.USER }}",
                            "method": "GET",
                        },
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "env.USER" in combined
        assert "env.HOST" not in combined.split("Missing env vars")[-1]

    def test_env_from_defaults_also_checked(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "defaults_env",
                "defaults": {"http": {"username": "{{ env.ADMIN_USER }}"}},
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {"url": "http://localhost/api", "method": "GET"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "env.ADMIN_USER" in combined


# ── Config schema hints ────────────────────────────────────────────


class TestConfigSchemaHints:
    def test_http_missing_url(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "no_url",
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {"method": "GET"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "'url' is missing or empty" in combined

    def test_http_empty_url(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "empty_url",
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {"method": "GET", "url": ""},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "'url' is missing or empty" in combined

    def test_http_valid_url_no_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "good_url",
                "steps": [
                    {
                        "name": "call",
                        "type": "http",
                        "config": {"method": "GET", "url": "http://example.com"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "'url' is missing or empty" not in combined

    def test_shell_missing_command(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "no_cmd",
                "steps": [
                    {
                        "name": "run",
                        "type": "shell",
                        "config": {},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "'command' is missing or empty" in combined

    def test_shell_valid_command_no_warning(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "good_cmd",
                "steps": [
                    {
                        "name": "run",
                        "type": "shell",
                        "config": {"command": "echo hi"},
                    },
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "'command' is missing or empty" not in combined


# ── Summary section ────────────────────────────────────────────────


class TestDryRunSummary:
    def test_dependency_summary_shown(self, tmp_path: Path):
        stdout, _, code = _dry_run(
            tmp_path,
            {
                "name": "dep_summary",
                "steps": [
                    {"name": "s1", "type": "shell", "config": {"command": "echo a"}},
                    {
                        "name": "s2",
                        "type": "shell",
                        "config": {"command": "echo {{ steps.s1.stdout }}"},
                    },
                ],
            },
        )
        assert code == 0
        assert "Step dependencies:" in stdout
        assert "s2 → s1" in stdout

    def test_no_dependency_summary_when_none(self, tmp_path: Path):
        stdout, _, code = _dry_run(
            tmp_path,
            {
                "name": "no_deps",
                "steps": [
                    {"name": "s1", "type": "shell", "config": {"command": "echo a"}},
                    {"name": "s2", "type": "shell", "config": {"command": "echo b"}},
                ],
            },
        )
        assert code == 0
        assert "Step dependencies:" not in stdout

    def test_warning_count_in_footer(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "warn_count",
                "steps": [
                    {"name": "s1", "type": "http", "config": {"method": "GET"}},
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "warning(s)" in combined

    def test_clean_run_no_warnings(self, tmp_path: Path):
        stdout, stderr, code = _dry_run(
            tmp_path,
            {
                "name": "clean",
                "steps": [
                    {"name": "s1", "type": "shell", "config": {"command": "echo ok"}},
                ],
            },
        )
        assert code == 0
        combined = stdout + stderr
        assert "warning(s)" not in combined
        assert "No steps were executed (dry-run)." in stdout
