"""Unit tests for cluster_info.main()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import cluster_info
from ontap_client import OntapClient


class TestClusterInfoMain:
    def _make_client(self) -> MagicMock:
        client = MagicMock(spec=OntapClient)
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        return client

    def test_fetches_cluster_endpoint(self) -> None:
        client = self._make_client()
        client.get.side_effect = [
            {"name": "cluster1", "version": {"full": "9.14.1"}},
            {"records": [], "num_records": 0},
        ]
        with patch.object(OntapClient, "from_env", return_value=client):
            cluster_info.main()
        first_call = client.get.call_args_list[0]
        assert first_call[0][0] == "/cluster"

    def test_fetches_nodes_endpoint(self) -> None:
        client = self._make_client()
        client.get.side_effect = [
            {"name": "cluster1", "version": {"full": "9.14.1"}},
            {"records": [], "num_records": 0},
        ]
        with patch.object(OntapClient, "from_env", return_value=client):
            cluster_info.main()
        second_call = client.get.call_args_list[1]
        assert second_call[0][0] == "/cluster/nodes"

    def test_handles_node_records(self) -> None:
        client = self._make_client()
        client.get.side_effect = [
            {"name": "cluster1", "version": {"full": "9.14.1"}},
            {
                "records": [
                    {"name": "node1", "serial_number": "SN-001"},
                    {"name": "node2", "serial_number": "SN-002"},
                ],
                "num_records": 2,
            },
        ]
        with patch.object(OntapClient, "from_env", return_value=client):
            # Should not raise
            cluster_info.main()

    def test_handles_missing_cluster_fields_gracefully(self) -> None:
        client = self._make_client()
        # Minimal response — missing 'name' and 'version'
        client.get.side_effect = [
            {},
            {"records": [], "num_records": 0},
        ]
        with patch.object(OntapClient, "from_env", return_value=client):
            cluster_info.main()  # Should not raise
