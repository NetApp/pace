# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.
"""Unit tests for shared helpers in snapmirror_cleanup_test_failover."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import snapmirror_cleanup_test_failover as sm_clean
from ontap_client import OntapClient


class TestEnv:
    def test_reads_from_inputs_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_clean.INPUTS, "CLUSTER_A", "10.5.0.1")
        assert sm_clean._env("CLUSTER_A") == "10.5.0.1"

    def test_falls_back_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_clean.INPUTS, "CLUSTER_A", "")
        monkeypatch.setenv("CLUSTER_A", "10.5.0.2")
        assert sm_clean._env("CLUSTER_A") == "10.5.0.2"

    def test_missing_required_key_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_clean.INPUTS, "CLUSTER_A", "")
        monkeypatch.delenv("CLUSTER_A", raising=False)
        with pytest.raises(SystemExit):
            sm_clean._env("CLUSTER_A")

    def test_returns_default_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_clean.INPUTS, "CLUSTER_A", "")
        monkeypatch.delenv("CLUSTER_A", raising=False)
        assert sm_clean._env("CLUSTER_A", default="fallback") == "fallback"


class TestPickClusterByRelationship:
    def _vol_client(self, records: list[dict]) -> MagicMock:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"records": records, "num_records": len(records)}
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        return client

    def test_picks_cluster_a_when_it_has_relationship(self) -> None:
        rel = {
            "uuid": "rel-uuid-1",
            "source": {"path": "vs0:vol_rw_01"},
            "destination": {"path": "vs1:vol_rw_01_dest"},
            "state": "snapmirrored",
            "healthy": True,
        }
        a_client = self._vol_client([rel])
        with patch("snapmirror_cleanup_test_failover.OntapClient", return_value=a_client):
            cluster, found_rel = sm_clean._pick_cluster_by_relationship(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vs0", "vol_rw_01"
            )
        assert cluster == "10.0.0.1"
        assert found_rel["uuid"] == "rel-uuid-1"

    def test_falls_through_to_cluster_b(self) -> None:
        rel = {
            "uuid": "rel-uuid-2",
            "source": {"path": "vs0:vol_rw_01"},
            "state": "snapmirrored",
        }
        a_client = self._vol_client([])
        b_client = self._vol_client([rel])
        with patch(
            "snapmirror_cleanup_test_failover.OntapClient", side_effect=[a_client, b_client]
        ):
            cluster, found_rel = sm_clean._pick_cluster_by_relationship(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vs0", "vol_rw_01"
            )
        assert cluster == "10.0.0.2"
        assert found_rel["uuid"] == "rel-uuid-2"

    def test_exits_when_neither_cluster_has_relationship(self) -> None:
        no_rel_client = self._vol_client([])
        with patch("snapmirror_cleanup_test_failover.OntapClient", return_value=no_rel_client):
            with pytest.raises(SystemExit):
                sm_clean._pick_cluster_by_relationship(
                    "10.0.0.1", "10.0.0.2", "admin", "pass", "vs0", "vol_rw_01"
                )

    def test_skips_unreachable_cluster_and_continues(self) -> None:
        rel = {"uuid": "rel-uuid-b", "source": {"path": "vs0:vol"}, "state": "snapmirrored"}
        a_client = MagicMock(spec=OntapClient)
        a_client.__enter__ = MagicMock(return_value=a_client)
        a_client.__exit__ = MagicMock(return_value=False)
        a_client.get.side_effect = ConnectionError("unreachable")
        b_client = self._vol_client([rel])
        with patch(
            "snapmirror_cleanup_test_failover.OntapClient", side_effect=[a_client, b_client]
        ):
            cluster, found_rel = sm_clean._pick_cluster_by_relationship(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vs0", "vol"
            )
        assert cluster == "10.0.0.2"

    def test_passes_source_path_filter(self) -> None:
        rel = {"uuid": "rel-uuid-x", "source": {"path": "vs0:myvol"}, "state": "snapmirrored"}
        a_client = self._vol_client([rel])
        with patch("snapmirror_cleanup_test_failover.OntapClient", return_value=a_client):
            sm_clean._pick_cluster_by_relationship(
                "10.0.0.1", "10.0.0.2", "admin", "pass", "vs0", "myvol"
            )
        call_kwargs = a_client.get.call_args[1]
        assert call_kwargs.get("source.path") == "vs0:myvol"
