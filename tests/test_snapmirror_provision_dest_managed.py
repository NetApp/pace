"""Unit tests for shared helpers in snapmirror_provision_dest_managed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import snapmirror_provision_dest_managed as sm_dst
from ontap_client import OntapClient

# ---------------------------------------------------------------------------
# _env
# ---------------------------------------------------------------------------


class TestEnv:
    def test_reads_from_inputs_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_dst.INPUTS, "SOURCE_HOST", "10.1.0.1")
        assert sm_dst._env("SOURCE_HOST") == "10.1.0.1"

    def test_falls_back_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_dst.INPUTS, "SOURCE_HOST", "")
        monkeypatch.setenv("SOURCE_HOST", "10.1.0.2")
        assert sm_dst._env("SOURCE_HOST") == "10.1.0.2"

    def test_missing_required_key_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_dst.INPUTS, "SOURCE_HOST", "")
        monkeypatch.delenv("SOURCE_HOST", raising=False)
        with pytest.raises(SystemExit):
            sm_dst._env("SOURCE_HOST")

    def test_returns_default_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_dst.INPUTS, "SOURCE_HOST", "")
        monkeypatch.delenv("SOURCE_HOST", raising=False)
        assert sm_dst._env("SOURCE_HOST", default="default_val") == "default_val"


# ---------------------------------------------------------------------------
# _poll_job
# ---------------------------------------------------------------------------


class TestPollJob:
    def test_returns_immediately_on_non_running_state(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "success"}
        result = sm_dst._poll_job(client, "job-uuid-1")
        assert result["state"] == "success"

    def test_polls_multiple_times_until_done(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.side_effect = [
            {"state": "running"},
            {"state": "success"},
        ]
        with patch("snapmirror_provision_dest_managed.time.sleep"):
            result = sm_dst._poll_job(client, "job-uuid-1", interval=1)
        assert result["state"] == "success"
        assert client.get.call_count == 2

    def test_passes_correct_url(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "success"}
        sm_dst._poll_job(client, "my-job-abc")
        assert "my-job-abc" in client.get.call_args[0][0]


# ---------------------------------------------------------------------------
# _wait_snapmirrored
# ---------------------------------------------------------------------------


class TestWaitSnapmirrored:
    def test_returns_immediately_when_snapmirrored(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "snapmirrored", "healthy": True}
        result = sm_dst._wait_snapmirrored(client, "rel-uuid", interval=1, max_wait=60)
        assert result["state"] == "snapmirrored"

    def test_polls_until_snapmirrored(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.side_effect = [
            {"state": "transferring"},
            {"state": "snapmirrored"},
        ]
        with patch("snapmirror_provision_dest_managed.time.sleep"):
            result = sm_dst._wait_snapmirrored(client, "rel-uuid", interval=1, max_wait=300)
        assert result["state"] == "snapmirrored"

    def test_raises_on_timeout(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"state": "transferring"}
        with patch("snapmirror_provision_dest_managed.time.sleep"):
            with pytest.raises(RuntimeError, match="Timed out"):
                sm_dst._wait_snapmirrored(client, "rel-uuid", interval=2, max_wait=1)


# ---------------------------------------------------------------------------
# _get_ic_lif_ips
# ---------------------------------------------------------------------------


class TestGetIcLifIps:
    def test_returns_intercluster_ips(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {
            "records": [
                {"ip": {"address": "10.0.0.10"}, "services": ["intercluster-core"]},
                {"ip": {"address": "10.0.0.11"}, "services": ["data-nfs"]},
            ]
        }
        ips = sm_dst._get_ic_lif_ips(client)
        assert ips == ["10.0.0.10"]

    def test_returns_empty_when_no_ic_lifs(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {
            "records": [
                {"ip": {"address": "10.0.0.11"}, "services": ["data-nfs"]},
            ]
        }
        ips = sm_dst._get_ic_lif_ips(client)
        assert ips == []

    def test_returns_empty_on_empty_records(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"records": []}
        ips = sm_dst._get_ic_lif_ips(client)
        assert ips == []

    def test_skips_records_with_no_ip_address(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {
            "records": [
                {"ip": {}, "services": ["intercluster-core"]},
            ]
        }
        ips = sm_dst._get_ic_lif_ips(client)
        assert ips == []


# ---------------------------------------------------------------------------
# _check_ic_lif_preconditions
# ---------------------------------------------------------------------------


class TestCheckIcLifPreconditions:
    def test_exits_when_no_src_ips(self) -> None:
        src = MagicMock(spec=OntapClient)
        dst = MagicMock(spec=OntapClient)
        with pytest.raises(SystemExit):
            sm_dst._check_ic_lif_preconditions(src, dst, [], ["10.0.0.1"])

    def test_exits_when_no_dst_ips(self) -> None:
        src = MagicMock(spec=OntapClient)
        dst = MagicMock(spec=OntapClient)
        with pytest.raises(SystemExit):
            sm_dst._check_ic_lif_preconditions(src, dst, ["10.0.0.1"], [])

    def test_no_error_when_same_subnet(self) -> None:
        src = MagicMock(spec=OntapClient)
        dst = MagicMock(spec=OntapClient)
        # Should not raise — same /24 subnet
        sm_dst._check_ic_lif_preconditions(src, dst, ["10.0.0.1"], ["10.0.0.2"])

    def test_warns_when_different_subnets(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        src = MagicMock(spec=OntapClient)
        dst = MagicMock(spec=OntapClient)
        with caplog.at_level(logging.WARNING, logger="snapmirror_provision_dest_managed"):
            sm_dst._check_ic_lif_preconditions(src, dst, ["10.0.0.1"], ["192.168.1.1"])
        assert any("subnet" in msg.lower() for msg in caplog.messages)
