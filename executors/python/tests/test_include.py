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

"""Tests for the step ``include`` directive."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from orchestrio.cli import cli
from orchestrio.parser import IncludeError, load_workflow


# ── Helpers ────────────────────────────────────────────────────────


def _write_fragment(tmp_path: Path, filename: str, fragment: dict) -> Path:
    p = tmp_path / filename
    p.write_text(yaml.dump(fragment))
    return p


def _write_workflow(tmp_path: Path, steps: list, **extra) -> Path:
    wf = {"name": "include-test", "version": "1", "steps": steps, **extra}
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(wf))
    return p


SIMPLE_FRAGMENT = {
    "name": "greet",
    "type": "shell",
    "config": {"command": "echo hello"},
}

HTTP_FRAGMENT = {
    "name": "fetch_data",
    "type": "http",
    "config": {
        "method": "GET",
        "url": "https://example.com/api",
        "headers": {"Accept": "application/json", "X-App": "test"},
        "timeout": 30,
    },
    "retry": {"attempts": 2, "delay_seconds": 5},
}


# ── Basic include resolution ──────────────────────────────────────


class TestIncludeBasic:
    def test_include_loads_fragment(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        wf = load_workflow(wf_path)
        assert len(wf.steps) == 1
        assert wf.steps[0].name == "greet"
        assert wf.steps[0].type == "shell"
        assert wf.steps[0].config["command"] == "echo hello"

    def test_include_preserves_retry(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "fetch.yaml"}])

        wf = load_workflow(wf_path)
        assert wf.steps[0].retry.attempts == 2
        assert wf.steps[0].retry.delay_seconds == 5

    def test_mixed_inline_and_include(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        steps = [
            {"name": "first", "type": "shell", "config": {"command": "echo first"}},
            {"include": "greet.yaml"},
            {"name": "last", "type": "shell", "config": {"command": "echo last"}},
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert len(wf.steps) == 3
        assert wf.steps[0].name == "first"
        assert wf.steps[1].name == "greet"
        assert wf.steps[2].name == "last"

    def test_multiple_includes(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        steps = [{"include": "greet.yaml"}, {"include": "fetch.yaml"}]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert len(wf.steps) == 2
        assert wf.steps[0].name == "greet"
        assert wf.steps[1].name == "fetch_data"


# ── Override merging ──────────────────────────────────────────────


class TestIncludeOverride:
    def test_override_name(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        steps = [{"include": "greet.yaml", "override": {"name": "custom_greet"}}]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.steps[0].name == "custom_greet"
        assert wf.steps[0].config["command"] == "echo hello"

    def test_override_config_deep_merges(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        steps = [
            {
                "include": "fetch.yaml",
                "override": {
                    "config": {
                        "url": "https://other.com/data",
                        "headers": {"Content-Type": "application/json"},
                    }
                },
            }
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        cfg = wf.steps[0].config
        assert cfg["url"] == "https://other.com/data"
        # Deep-merged: original Accept + X-App preserved, Content-Type added
        assert cfg["headers"]["Accept"] == "application/json"
        assert cfg["headers"]["X-App"] == "test"
        assert cfg["headers"]["Content-Type"] == "application/json"
        # Non-overridden config preserved
        assert cfg["timeout"] == 30

    def test_override_config_leaf_wins(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        steps = [
            {
                "include": "fetch.yaml",
                "override": {"config": {"timeout": 99}},
            }
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.steps[0].config["timeout"] == 99

    def test_override_retry(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        steps = [
            {
                "include": "fetch.yaml",
                "override": {"retry": {"attempts": 10, "delay_seconds": 1}},
            }
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.steps[0].retry.attempts == 10
        assert wf.steps[0].retry.delay_seconds == 1

    def test_override_on_failure(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        steps = [
            {"include": "greet.yaml", "override": {"on_failure": "continue"}}
        ]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        assert wf.steps[0].on_failure.value == "continue"

    def test_no_override_returns_fragment_unchanged(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        steps = [{"include": "fetch.yaml"}]
        wf_path = _write_workflow(tmp_path, steps)

        wf = load_workflow(wf_path)
        cfg = wf.steps[0].config
        assert cfg["method"] == "GET"
        assert cfg["url"] == "https://example.com/api"
        assert cfg["timeout"] == 30


# ── Subdirectory paths ────────────────────────────────────────────


class TestIncludePaths:
    def test_relative_to_workflow_file(self, tmp_path: Path) -> None:
        frags = tmp_path / "frags"
        frags.mkdir()
        _write_fragment(frags, "greet.yaml", SIMPLE_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "frags/greet.yaml"}])

        wf = load_workflow(wf_path)
        assert wf.steps[0].name == "greet"

    def test_parent_relative_path(self, tmp_path: Path) -> None:
        frags = tmp_path / "steps"
        frags.mkdir()
        _write_fragment(frags, "greet.yaml", SIMPLE_FRAGMENT)

        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        wf_path = _write_workflow(wf_dir, [{"include": "../steps/greet.yaml"}])

        wf = load_workflow(wf_path)
        assert wf.steps[0].name == "greet"

    def test_dict_source_uses_base_dir(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        data = {
            "name": "dict-wf",
            "version": "1",
            "steps": [{"include": "greet.yaml"}],
        }
        wf = load_workflow(data, base_dir=tmp_path)
        assert wf.steps[0].name == "greet"


# ── Error handling ────────────────────────────────────────────────


class TestIncludeErrors:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        wf_path = _write_workflow(tmp_path, [{"include": "nope.yaml"}])
        with pytest.raises(IncludeError, match="not found"):
            load_workflow(wf_path)

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(":\n  :\n    [invalid")
        wf_path = _write_workflow(tmp_path, [{"include": "bad.yaml"}])
        with pytest.raises(IncludeError, match="invalid YAML"):
            load_workflow(wf_path)

    def test_non_mapping_fragment_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "list.yaml"
        bad.write_text("- item1\n- item2\n")
        wf_path = _write_workflow(tmp_path, [{"include": "list.yaml"}])
        with pytest.raises(IncludeError, match="YAML mapping"):
            load_workflow(wf_path)

    def test_fragment_missing_name_raises(self, tmp_path: Path) -> None:
        bad_frag = tmp_path / "noname.yaml"
        bad_frag.write_text(yaml.dump({"type": "shell", "config": {"command": "echo"}}))
        wf_path = _write_workflow(tmp_path, [{"include": "noname.yaml"}])
        with pytest.raises(IncludeError, match="must define 'name' and 'type'"):
            load_workflow(wf_path)

    def test_fragment_missing_type_raises(self, tmp_path: Path) -> None:
        bad_frag = tmp_path / "notype.yaml"
        bad_frag.write_text(yaml.dump({"name": "s1", "config": {"command": "echo"}}))
        wf_path = _write_workflow(tmp_path, [{"include": "notype.yaml"}])
        with pytest.raises(IncludeError, match="must define 'name' and 'type'"):
            load_workflow(wf_path)

    def test_error_message_contains_step_index(self, tmp_path: Path) -> None:
        inline = {"name": "first", "type": "shell", "config": {"command": "echo"}}
        steps = [inline, {"include": "missing.yaml"}]
        wf_path = _write_workflow(tmp_path, steps)
        with pytest.raises(IncludeError, match="Step 1"):
            load_workflow(wf_path)


# ── CLI integration ───────────────────────────────────────────────


class TestIncludeCLI:
    def test_validate_with_include(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf_path)])
        assert result.exit_code == 0
        assert "Valid workflow" in result.output

    def test_run_with_include(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        wf_path = _write_workflow(tmp_path, [{"include": "greet.yaml"}])

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--no-log"])
        assert result.exit_code == 0
        assert '"status": "success"' in result.output

    def test_dry_run_with_include(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "greet.yaml", SIMPLE_FRAGMENT)
        wf_path = _write_workflow(
            tmp_path,
            [
                {"include": "greet.yaml", "override": {"name": "my_greet"}},
            ],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "my_greet" in result.output

    def test_include_combined_with_defaults(self, tmp_path: Path) -> None:
        _write_fragment(tmp_path, "fetch.yaml", HTTP_FRAGMENT)
        wf_path = _write_workflow(
            tmp_path,
            [{"include": "fetch.yaml"}],
            defaults={"http": {"verify_ssl": False, "username": "admin"}},
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf_path), "--dry-run"])
        assert result.exit_code == 0
        assert "verify_ssl" in result.output
        assert "admin" in result.output
