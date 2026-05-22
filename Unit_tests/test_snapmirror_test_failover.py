# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.
"""Unit tests for shared helpers in snapmirror_test_failover."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import snapmirror_test_failover as sm_tf
from ontap_client import OntapClient


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


class TestPickCluster:
    def _make_client(self, records: list[dict]) -> MagicMock:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"records": records, "num_records": len(records)}
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
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
        a_client = self._make_client([])
        b_client = self._make_client([vol])
        with patch("snapmirror_test_failover.OntapClient", side_effect=[a_client, b_client]):
            cluster, found_vol = sm_tf._pick_cluster(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vol_rw_01"
            )
        assert cluster == "10.0.0.2"

    def test_exits_when_no_cluster_has_dp_volume(self) -> None:
        no_vol_client = self._make_client([])
        with patch("snapmirror_test_failover.OntapClient", return_value=no_vol_client):
            with pytest.raises(SystemExit):
                sm_tf._pick_cluster("10.0.0.1", "10.0.0.2", "admin", "pass", "vol_rw_01")

    def test_uses_wildcard_filter_in_auto_mode(self) -> None:
        no_vol_client = self._make_client([])
        with patch("snapmirror_test_failover.OntapClient", return_value=no_vol_client):
            with pytest.raises(SystemExit):
                sm_tf._pick_cluster("10.0.0.1", "10.0.0.2", "admin", "pass", "*")
        call_kwargs = no_vol_client.get.call_args[1]
        assert call_kwargs.get("name") == "*_dest"

    def test_skips_unreachable_cluster_and_continues(self) -> None:
        vol = {"name": "vol_01_dest", "uuid": "v-uuid", "svm": {"name": "vs1"}}
        a_client = MagicMock(spec=OntapClient)
        a_client.__enter__ = MagicMock(return_value=a_client)
        a_client.__exit__ = MagicMock(return_value=False)
        a_client.get.side_effect = ConnectionError("unreachable")
        b_client = self._make_client([vol])
        with patch("snapmirror_test_failover.OntapClient", side_effect=[a_client, b_client]):
            cluster, found_vol = sm_tf._pick_cluster(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vol_01"
            )
        assert cluster == "10.0.0.2"
