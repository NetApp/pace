"""Unit tests for cluster_setup_basic helper functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import cluster_setup_basic as csb
import pytest
from ontap_client import OntapClient

# ---------------------------------------------------------------------------
# _env
# ---------------------------------------------------------------------------


class TestEnv:
    def test_reads_from_inputs_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(csb.INPUTS, "CLUSTER_NAME", "mycluster")
        assert csb._env("CLUSTER_NAME") == "mycluster"

    def test_falls_back_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(csb.INPUTS, "CLUSTER_NAME", "")
        monkeypatch.setenv("CLUSTER_NAME", "envcluster")
        assert csb._env("CLUSTER_NAME") == "envcluster"

    def test_inputs_takes_priority_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(csb.INPUTS, "CLUSTER_NAME", "from_inputs")
        monkeypatch.setenv("CLUSTER_NAME", "from_env")
        assert csb._env("CLUSTER_NAME") == "from_inputs"

    def test_missing_required_key_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(csb.INPUTS, "CLUSTER_NAME", "")
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        with pytest.raises(SystemExit):
            csb._env("CLUSTER_NAME", required=True)

    def test_missing_optional_key_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(csb.INPUTS, "CLUSTER_NAME", "")
        monkeypatch.delenv("CLUSTER_NAME", raising=False)
        result = csb._env("CLUSTER_NAME", required=False)
        assert result == ""


# ---------------------------------------------------------------------------
# _load_env_file (cluster_setup_basic version — loads into INPUTS dict)
# ---------------------------------------------------------------------------


class TestLoadEnvFileCSB:
    def test_valid_file_updates_inputs(self, tmp_path: Path) -> None:
        env_file = tmp_path / "build.env"
        env_file.write_text("CLUSTER_NAME=testcluster\nCLUSTER_PASS=secret\n")
        original = dict(csb.INPUTS)
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "testcluster"
        assert csb.INPUTS["CLUSTER_PASS"] == "secret"
        # restore
        csb.INPUTS.update(original)

    def test_strips_double_quotes_from_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / "quoted.env"
        env_file.write_text('CLUSTER_NAME="quoted-name"\n')
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "quoted-name"

    def test_strips_single_quotes_from_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / "single.env"
        env_file.write_text("CLUSTER_NAME='single-name'\n")
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "single-name"

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        env_file = tmp_path / "blanks.env"
        env_file.write_text("\n\nCLUSTER_NAME=ok\n\n")
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "ok"

    def test_comment_lines_skipped(self, tmp_path: Path) -> None:
        env_file = tmp_path / "comments.env"
        env_file.write_text("# a comment\nCLUSTER_NAME=fromcomment\n")
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "fromcomment"

    def test_lines_without_equals_skipped(self, tmp_path: Path) -> None:
        """Lines without '=' are silently skipped (no sys.exit in this version)."""
        env_file = tmp_path / "noeq.env"
        env_file.write_text("CLUSTER_NAME=safe\nNO_EQUALS\n")
        csb._load_env_file(str(env_file))
        assert csb.INPUTS["CLUSTER_NAME"] == "safe"


# ---------------------------------------------------------------------------
# _get_nodes
# ---------------------------------------------------------------------------


class TestGetNodes:
    def test_returns_result_on_first_try(self) -> None:
        client = MagicMock(spec=OntapClient)
        expected = {"records": [{"name": "node1"}], "num_records": 1}
        client.get.return_value = expected
        result = csb._get_nodes(client, membership="available")
        assert result == expected

    def test_falls_back_on_262197_error(self) -> None:
        client = MagicMock(spec=OntapClient)
        fallback = {"records": [{"name": "node1"}], "num_records": 1}
        client.get.side_effect = [
            RuntimeError("error code 262197"),
            fallback,
        ]
        result = csb._get_nodes(client)
        assert result == fallback
        assert client.get.call_count == 2

    def test_raises_immediately_on_non_262197_error(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.side_effect = RuntimeError("some other error 999")
        with pytest.raises(RuntimeError, match="999"):
            csb._get_nodes(client)
        assert client.get.call_count == 1

    def test_raises_last_exc_when_all_field_sets_fail(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.side_effect = RuntimeError("error code 262197")
        with pytest.raises(RuntimeError):
            csb._get_nodes(client)


# ---------------------------------------------------------------------------
# discover_nodes
# ---------------------------------------------------------------------------


class TestDiscoverNodes:
    def test_returns_node_list_on_success(self) -> None:
        client = MagicMock(spec=OntapClient)
        expected = {"records": [{"name": "node1"}], "num_records": 1}
        with patch.object(csb, "_get_nodes", return_value=expected):
            result = csb.discover_nodes(client)
        assert result == expected

    def test_retries_then_succeeds(self) -> None:
        client = MagicMock(spec=OntapClient)
        success = {"records": [{"name": "node1"}], "num_records": 1}
        with (
            patch.object(csb, "_get_nodes", side_effect=[RuntimeError("transient"), success]),
            patch("cluster_setup_basic.time.sleep"),
        ):
            result = csb.discover_nodes(client, attempts=3, delay=0)
        assert result == success

    def test_raises_runtime_error_after_all_attempts(self) -> None:
        client = MagicMock(spec=OntapClient)
        with (
            patch.object(csb, "_get_nodes", side_effect=RuntimeError("persistent")),
            patch("cluster_setup_basic.time.sleep"),
        ):
            with pytest.raises(RuntimeError, match="failed after 2 attempts"):
                csb.discover_nodes(client, attempts=2, delay=0)


# ---------------------------------------------------------------------------
# discover_local
# ---------------------------------------------------------------------------


class TestDiscoverLocal:
    def test_returns_result_when_records_present(self) -> None:
        client = MagicMock(spec=OntapClient)
        expected = {"records": [{"name": "node1", "uuid": "uuid-1"}], "num_records": 1}
        with patch.object(csb, "_get_nodes", return_value=expected):
            result = csb.discover_local(client)
        assert result == expected

    def test_raises_when_no_records(self) -> None:
        client = MagicMock(spec=OntapClient)
        with patch.object(csb, "_get_nodes", return_value={"records": [], "num_records": 0}):
            with pytest.raises(RuntimeError, match="no local node"):
                csb.discover_local(client)


# ---------------------------------------------------------------------------
# discover_partner
# ---------------------------------------------------------------------------


class TestDiscoverPartner:
    def test_returns_result_when_records_present(self) -> None:
        client = MagicMock(spec=OntapClient)
        expected = {"records": [{"name": "node2", "uuid": "uuid-2"}], "num_records": 1}
        with patch.object(csb, "_get_nodes", return_value=expected):
            result = csb.discover_partner(client, local_uuid="uuid-1")
        assert result == expected

    def test_passes_exclusion_filter(self) -> None:
        client = MagicMock(spec=OntapClient)
        expected = {"records": [{"name": "node2"}], "num_records": 1}
        with patch.object(csb, "_get_nodes", return_value=expected) as mock_get:
            csb.discover_partner(client, local_uuid="uuid-1")
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("uuid") == "!uuid-1"

    def test_raises_when_no_records(self) -> None:
        client = MagicMock(spec=OntapClient)
        with patch.object(csb, "_get_nodes", return_value={"records": [], "num_records": 0}):
            with pytest.raises(RuntimeError, match="no partner node"):
                csb.discover_partner(client, local_uuid="uuid-1")
