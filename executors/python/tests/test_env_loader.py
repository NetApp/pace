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

"""Tests for orchestrio.env_loader."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
import yaml

from orchestrio.env_loader import (
    EnvLoadError,
    load_env_file,
    merge_env,
    parse_env_pairs,
)


# ── load_env_file: .env format ─────────────────────────────────────


class TestLoadDotenv:
    def test_basic_key_value(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("HOST=localhost\nPORT=8080\n")
        assert load_env_file(f) == {"HOST": "localhost", "PORT": "8080"}

    def test_strips_quotes(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("KEY=\"hello world\"\nKEY2='single'\n")
        assert load_env_file(f) == {"KEY": "hello world", "KEY2": "single"}

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("# comment\n\nFOO=bar\n  # another comment\n")
        assert load_env_file(f) == {"FOO": "bar"}

    def test_empty_value(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("EMPTY=\n")
        assert load_env_file(f) == {"EMPTY": ""}

    def test_value_with_equals(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("CONN=host=db;port=5432\n")
        assert load_env_file(f) == {"CONN": "host=db;port=5432"}

    def test_missing_equals_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "test.env"
        f.write_text("BADLINE\n")
        with pytest.raises(EnvLoadError, match="expected KEY=VALUE"):
            load_env_file(f)

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(EnvLoadError, match="not found"):
            load_env_file(tmp_path / "nope.env")


# ── load_env_file: YAML format ────────────────────────────────────


class TestLoadYaml:
    def test_flat_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text(yaml.dump({"HOST": "10.0.0.1", "PORT": 443}))
        result = load_env_file(f)
        assert result == {"HOST": "10.0.0.1", "PORT": "443"}

    def test_yml_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yml"
        f.write_text(yaml.dump({"A": "1"}))
        assert load_env_file(f) == {"A": "1"}

    def test_empty_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text("")
        assert load_env_file(f) == {}

    def test_nested_yaml_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text(yaml.dump({"A": {"nested": "bad"}}))
        with pytest.raises(EnvLoadError, match="nested values are not allowed"):
            load_env_file(f)

    def test_non_dict_yaml_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text("- item1\n- item2\n")
        with pytest.raises(EnvLoadError, match="flat key-value mapping"):
            load_env_file(f)

    def test_none_values_coerced(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text("KEY:\n")
        assert load_env_file(f) == {"KEY": ""}


# ── load_env_file: JSON format ────────────────────────────────────


class TestLoadJson:
    def test_flat_json(self, tmp_path: Path) -> None:
        f = tmp_path / "env.json"
        f.write_text(json.dumps({"HOST": "db", "PORT": "5432"}))
        assert load_env_file(f) == {"HOST": "db", "PORT": "5432"}

    def test_non_dict_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "env.json"
        f.write_text(json.dumps([1, 2, 3]))
        with pytest.raises(EnvLoadError, match="flat key-value object"):
            load_env_file(f)

    def test_nested_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "env.json"
        f.write_text(json.dumps({"A": {"nested": True}}))
        with pytest.raises(EnvLoadError, match="nested values are not allowed"):
            load_env_file(f)


# ── parse_env_pairs ────────────────────────────────────────────────


class TestParseEnvPairs:
    def test_basic_pairs(self) -> None:
        assert parse_env_pairs(("A=1", "B=hello")) == {"A": "1", "B": "hello"}

    def test_empty_value(self) -> None:
        assert parse_env_pairs(("KEY=",)) == {"KEY": ""}

    def test_value_with_equals(self) -> None:
        assert parse_env_pairs(("CONN=host=db;port=5432",)) == {"CONN": "host=db;port=5432"}

    def test_missing_equals_raises(self) -> None:
        with pytest.raises(EnvLoadError, match="expected KEY=VALUE"):
            parse_env_pairs(("NOEQUALS",))

    def test_empty_key_raises(self) -> None:
        with pytest.raises(EnvLoadError, match="empty key"):
            parse_env_pairs(("=value",))

    def test_empty_tuple(self) -> None:
        assert parse_env_pairs(()) == {}


# ── merge_env (precedence) ────────────────────────────────────────


class TestMergeEnv:
    def test_yaml_defaults_only(self) -> None:
        result = merge_env({"A": "yaml"}, {}, {})
        assert result == {"A": "yaml"}

    def test_env_file_overrides_yaml(self) -> None:
        result = merge_env({"A": "yaml"}, {"A": "file"}, {})
        assert result == {"A": "file"}

    def test_cli_overrides_env_file(self) -> None:
        result = merge_env({"A": "yaml"}, {"A": "file"}, {"A": "cli"})
        assert result == {"A": "cli"}

    def test_cli_overrides_everything(self) -> None:
        with mock.patch.dict("os.environ", {"A": "os"}):
            result = merge_env({"A": "yaml"}, {"A": "file"}, {"A": "cli"})
        assert result == {"A": "cli"}

    def test_os_environ_scoped_to_yaml_keys(self) -> None:
        with mock.patch.dict("os.environ", {"A": "os", "SECRET": "leaked"}):
            result = merge_env({"A": "yaml"}, {}, {})
        assert result == {"A": "os"}
        assert "SECRET" not in result

    def test_os_environ_overrides_yaml_but_not_env_file(self) -> None:
        with mock.patch.dict("os.environ", {"A": "os"}):
            result = merge_env({"A": "yaml"}, {"A": "file"}, {})
        assert result == {"A": "file"}

    def test_env_file_adds_new_keys(self) -> None:
        result = merge_env({"A": "yaml"}, {"B": "new"}, {})
        assert result == {"A": "yaml", "B": "new"}

    def test_cli_adds_new_keys(self) -> None:
        result = merge_env({"A": "yaml"}, {}, {"C": "extra"})
        assert result == {"A": "yaml", "C": "extra"}

    def test_full_precedence_chain(self) -> None:
        with mock.patch.dict("os.environ", {"A": "os", "B": "os"}):
            result = merge_env(
                {"A": "yaml", "B": "yaml", "C": "yaml"},
                {"A": "file", "D": "file"},
                {"A": "cli", "E": "cli"},
            )
        assert result == {
            "A": "cli",  # cli wins over file, os, yaml
            "B": "os",  # os wins over yaml (scoped key)
            "C": "yaml",  # only yaml default
            "D": "file",  # new key from env-file
            "E": "cli",  # new key from cli
        }
