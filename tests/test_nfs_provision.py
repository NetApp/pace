"""Unit tests for nfs_provision helper functions."""

from __future__ import annotations

import os
from pathlib import Path

import nfs_provision
import pytest


class TestLoadEnvFile:
    def test_valid_file_sets_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "test.env"
        env_file.write_text("FOO_NFS=bar\nBAZ_NFS=qux\n")
        monkeypatch.delenv("FOO_NFS", raising=False)
        monkeypatch.delenv("BAZ_NFS", raising=False)
        nfs_provision._load_env_file(str(env_file))
        assert os.environ["FOO_NFS"] == "bar"
        assert os.environ["BAZ_NFS"] == "qux"

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            nfs_provision._load_env_file(str(tmp_path / "nonexistent.env"))

    def test_malformed_line_no_equals_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "bad.env"
        env_file.write_text("VALID=ok\nNO_EQUALS_HERE\n")
        monkeypatch.delenv("VALID", raising=False)
        with pytest.raises(SystemExit):
            nfs_provision._load_env_file(str(env_file))

    def test_blank_lines_are_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "blanks.env"
        env_file.write_text("\n\nKEY_NFS2=value\n\n")
        monkeypatch.delenv("KEY_NFS2", raising=False)
        nfs_provision._load_env_file(str(env_file))
        assert os.environ["KEY_NFS2"] == "value"

    def test_comment_lines_are_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "comments.env"
        env_file.write_text("# this is a comment\nKEY_NFS3=value\n")
        monkeypatch.delenv("KEY_NFS3", raising=False)
        nfs_provision._load_env_file(str(env_file))
        assert os.environ["KEY_NFS3"] == "value"

    def test_setdefault_does_not_override_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "override.env"
        env_file.write_text("KEY_NFS4=from_file\n")
        monkeypatch.setenv("KEY_NFS4", "already_set")
        nfs_provision._load_env_file(str(env_file))
        assert os.environ["KEY_NFS4"] == "already_set"

    def test_value_with_equals_sign_handled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Values containing '=' are preserved (partition only splits on first '=')."""
        env_file = tmp_path / "equals.env"
        env_file.write_text("KEY_NFS5=a=b=c\n")
        monkeypatch.delenv("KEY_NFS5", raising=False)
        nfs_provision._load_env_file(str(env_file))
        assert os.environ["KEY_NFS5"] == "a=b=c"
