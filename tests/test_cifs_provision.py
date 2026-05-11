"""Unit tests for cifs_provision helper functions."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import cifs_provision
import pytest
from ontap_client import OntapClient

# ---------------------------------------------------------------------------
# _load_env_file  (same dotenv-into-os.environ implementation as nfs_provision)
# ---------------------------------------------------------------------------


class TestLoadEnvFile:
    def test_valid_file_sets_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "test.env"
        env_file.write_text("CIFS_FOO=bar\nCIFS_BAZ=qux\n")
        monkeypatch.delenv("CIFS_FOO", raising=False)
        monkeypatch.delenv("CIFS_BAZ", raising=False)
        cifs_provision._load_env_file(str(env_file))
        assert os.environ["CIFS_FOO"] == "bar"
        assert os.environ["CIFS_BAZ"] == "qux"

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            cifs_provision._load_env_file(str(tmp_path / "nonexistent.env"))

    def test_malformed_line_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / "bad.env"
        env_file.write_text("CIFS_OK=yes\nNO_EQUALS\n")
        monkeypatch.delenv("CIFS_OK", raising=False)
        with pytest.raises(SystemExit):
            cifs_provision._load_env_file(str(env_file))

    def test_blank_and_comment_lines_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "mixed.env"
        env_file.write_text("# comment\n\nCIFS_KEY=value\n")
        monkeypatch.delenv("CIFS_KEY", raising=False)
        cifs_provision._load_env_file(str(env_file))
        assert os.environ["CIFS_KEY"] == "value"

    def test_setdefault_does_not_override_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "override.env"
        env_file.write_text("CIFS_KEY2=from_file\n")
        monkeypatch.setenv("CIFS_KEY2", "already_set")
        cifs_provision._load_env_file(str(env_file))
        assert os.environ["CIFS_KEY2"] == "already_set"


# ---------------------------------------------------------------------------
# _pick
# ---------------------------------------------------------------------------


class TestPick:
    def test_cli_val_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SVM_NAME", "from_env")
        monkeypatch.setitem(cifs_provision.ENV, "SVM_NAME", "from_env_dict")
        assert cifs_provision._pick("from_cli", "SVM_NAME") == "from_cli"

    def test_env_var_second_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SVM_NAME", "from_env")
        monkeypatch.setitem(cifs_provision.ENV, "SVM_NAME", "from_env_dict")
        assert cifs_provision._pick(None, "SVM_NAME") == "from_env"

    def test_env_dict_third_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SVM_NAME", raising=False)
        monkeypatch.setitem(cifs_provision.ENV, "SVM_NAME", "from_env_dict")
        assert cifs_provision._pick(None, "SVM_NAME") == "from_env_dict"

    def test_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_KEY", raising=False)
        assert cifs_provision._pick(None, "MISSING_KEY", "fallback") == "fallback"

    def test_empty_string_cli_treated_as_falsy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SVM_NAME", "from_env")
        assert cifs_provision._pick("", "SVM_NAME") == "from_env"


# ---------------------------------------------------------------------------
# _resolve_config
# ---------------------------------------------------------------------------


class TestResolveConfig:
    def _make_args(self, **overrides):
        import argparse

        defaults = {
            "env_file": None,
            "svm": None,
            "volume": None,
            "size": None,
            "aggregate": "aggr1",
            "share_name": None,
            "share_comment": None,
            "acl_user": None,
            "acl_permission": None,
            "create_cifs_server": False,
            "cifs_server_name": None,
            "workgroup": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_missing_aggregate_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGGR_NAME", raising=False)
        monkeypatch.setitem(cifs_provision.ENV, "AGGR_NAME", "")
        args = self._make_args(aggregate=None)
        with pytest.raises(SystemExit):
            cifs_provision._resolve_config(args)

    def test_aggregate_from_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGGR_NAME", raising=False)
        args = self._make_args(aggregate="aggr_from_cli")
        config = cifs_provision._resolve_config(args)
        assert config["aggregate"] == "aggr_from_cli"

    def test_create_cifs_server_flag_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        args = self._make_args(create_cifs_server=True)
        config = cifs_provision._resolve_config(args)
        assert config["create_cifs_server"] is True

    def test_returns_all_expected_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        args = self._make_args()
        config = cifs_provision._resolve_config(args)
        expected_keys = {
            "svm",
            "volume",
            "size",
            "aggregate",
            "share_name",
            "share_comment",
            "acl_user",
            "acl_permission",
            "create_cifs_server",
            "cifs_server_name",
            "workgroup",
        }
        assert expected_keys == set(config.keys())


# ---------------------------------------------------------------------------
# _ensure_cifs_server
# ---------------------------------------------------------------------------


class TestEnsureCifsServer:
    def _make_client(self) -> MagicMock:
        client = MagicMock(spec=OntapClient)
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        return client

    def test_server_exists_no_create_called(self) -> None:
        client = self._make_client()
        client.get.return_value = {
            "records": [{"svm": {"name": "vs1"}, "enabled": True}],
            "num_records": 1,
        }
        # Should not raise or call post
        cifs_provision._ensure_cifs_server(client, "vs1", False, "ONTAP-CIFS", "WORKGROUP")
        client.post.assert_not_called()

    def test_no_server_no_flag_exits(self) -> None:
        client = self._make_client()
        client.get.return_value = {"records": [], "num_records": 0}
        with pytest.raises(SystemExit):
            cifs_provision._ensure_cifs_server(client, "vs1", False, "ONTAP-CIFS", "WORKGROUP")

    def test_no_server_with_flag_creates_server(self) -> None:
        client = self._make_client()
        client.get.return_value = {"records": [], "num_records": 0}
        client.post.return_value = {}  # no async job
        cifs_provision._ensure_cifs_server(client, "vs1", True, "MY-CIFS", "MYGROUP")
        client.post.assert_called_once()
        # post(path, body) — body is the second positional arg
        call_args, call_kwargs = client.post.call_args
        call_body = call_args[1] if len(call_args) > 1 else call_kwargs.get("body", {})
        assert call_body["name"] == "MY-CIFS"
        assert call_body["workgroup"] == "MYGROUP"

    def test_no_server_with_flag_polls_job_when_returned(self) -> None:
        client = self._make_client()
        client.get.return_value = {"records": [], "num_records": 0}
        client.post.return_value = {"job": {"uuid": "job-uuid-1"}}
        cifs_provision._ensure_cifs_server(client, "vs1", True, "MY-CIFS", "MYGROUP")
        client.poll_job.assert_called_once_with("job-uuid-1")
