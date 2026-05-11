"""Unit tests for shared helpers in snapmirror_test_failover."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import snapmirror_test_failover as sm_tf
from ontap_client import OntapClient

# ---------------------------------------------------------------------------
# _env
# ---------------------------------------------------------------------------


class TestEnv:
    def test_reads_from_inputs_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_tf.INPUTS, "CLUSTER_A", "10.0.1.1")
        assert sm_tf._env("CLUSTER_A") == "10.0.1.1"

    def test_falls_back_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_tf.INPUTS, "CLUSTER_A", "")
        monkeypatch.setenv("CLUSTER_A", "10.0.1.2")
        assert sm_tf._env("CLUSTER_A") == "10.0.1.2"

    def test_missing_required_key_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_tf.INPUTS, "CLUSTER_A", "")
        monkeypatch.delenv("CLUSTER_A", raising=False)
        with pytest.raises(SystemExit):
            sm_tf._env("CLUSTER_A")

    def test_returns_default_when_not_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_tf.INPUTS, "CLUSTER_A", "")
        monkeypatch.delenv("CLUSTER_A", raising=False)
        assert sm_tf._env("CLUSTER_A", default="x") == "x"


# ---------------------------------------------------------------------------
# _poll_job
# ---------------------------------------------------------------------------


class TestPollJob:
    def test_returns_on_first_non_running_state(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "success"}
        result = sm_tf._poll_job(client, "job-1")
        assert result["state"] == "success"

    def test_polls_until_done(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.side_effect = [{"state": "running"}, {"state": "success"}]
        with patch("snapmirror_test_failover.time.sleep"):
            result = sm_tf._poll_job(client, "job-1", interval=1)
        assert client.get.call_count == 2
        assert result["state"] == "success"


# ---------------------------------------------------------------------------
# _wait_snapmirrored
# ---------------------------------------------------------------------------


class TestWaitSnapmirrored:
    def test_returns_immediately_when_snapmirrored(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "snapmirrored"}
        result = sm_tf._wait_snapmirrored(client, "rel-uuid", interval=1, max_wait=60)
        assert result["state"] == "snapmirrored"

    def test_raises_timeout_when_never_converges(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "transferring"}
        with patch("snapmirror_test_failover.time.sleep"):
            with pytest.raises(RuntimeError, match="Timed out"):
                sm_tf._wait_snapmirrored(client, "rel-uuid", interval=2, max_wait=1)


# ---------------------------------------------------------------------------
# _pick_cluster
# ---------------------------------------------------------------------------


class TestPickCluster:
    def _make_client(self, records: list[dict]) -> MagicMock:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {
            "records": records,
            "num_records": len(records),
        }
        return client

    def test_picks_cluster_a_when_it_has_dp_volume(self) -> None:
        vol = {"name": "vol_rw_01_dest", "uuid": "v-uuid", "svm": {"name": "vs1"}}
        with patch("snapmirror_test_failover.OntapClient") as MockClient:
            instance = self._make_client([vol])
            MockClient.return_value = instance
            cluster, found_vol = sm_tf._pick_cluster(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vol_rw_01"
            )
        assert cluster == "10.0.0.1"
        assert found_vol["name"] == "vol_rw_01_dest"

    def test_falls_through_to_cluster_b(self) -> None:
        vol = {"name": "vol_rw_01_dest", "uuid": "v-uuid", "svm": {"name": "vs1"}}
        a_client = MagicMock(spec=OntapClient)
        a_client.get.return_value = {"records": [], "num_records": 0}
        b_client = MagicMock(spec=OntapClient)
        b_client.get.return_value = {"records": [vol], "num_records": 1}

        with patch("snapmirror_test_failover.OntapClient", side_effect=[a_client, b_client]):
            cluster, found_vol = sm_tf._pick_cluster(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vol_rw_01"
            )
        assert cluster == "10.0.0.2"

    def test_exits_when_no_cluster_has_dp_volume(self) -> None:
        no_vol_client = MagicMock(spec=OntapClient)
        no_vol_client.get.return_value = {"records": [], "num_records": 0}

        with patch("snapmirror_test_failover.OntapClient", return_value=no_vol_client):
            with pytest.raises(SystemExit):
                sm_tf._pick_cluster("10.0.0.1", "10.0.0.2", "admin", "pass", "vol_rw_01")

    def test_uses_wildcard_filter_in_auto_mode(self) -> None:
        """When vol_name_filter='*', the DP name filter should be '*_dest'."""
        no_vol_client = MagicMock(spec=OntapClient)
        no_vol_client.get.return_value = {"records": [], "num_records": 0}

        with patch("snapmirror_test_failover.OntapClient", return_value=no_vol_client):
            with pytest.raises(SystemExit):
                sm_tf._pick_cluster("10.0.0.1", "10.0.0.2", "admin", "pass", "*")

        # Verify the filter sent was '*_dest'
        call_kwargs = no_vol_client.get.call_args[1]
        assert call_kwargs.get("name") == "*_dest"

    def test_skips_unreachable_cluster_and_continues(self) -> None:
        vol = {"name": "vol_01_dest", "uuid": "v-uuid", "svm": {"name": "vs1"}}
        a_client = MagicMock(spec=OntapClient)
        a_client.get.side_effect = ConnectionError("unreachable")
        b_client = MagicMock(spec=OntapClient)
        b_client.get.return_value = {"records": [vol], "num_records": 1}

        with patch("snapmirror_test_failover.OntapClient", side_effect=[a_client, b_client]):
            cluster, found_vol = sm_tf._pick_cluster(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vol_01"
            )
        assert cluster == "10.0.0.2"
