"""Unit tests for shared helpers in snapmirror_provision_src_managed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import snapmirror_provision_src_managed as sm_src
from ontap_client import OntapClient

# ---------------------------------------------------------------------------
# _env
# ---------------------------------------------------------------------------


class TestEnv:
    def test_reads_from_inputs_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_src.INPUTS, "SOURCE_HOST", "10.0.0.1")
        assert sm_src._env("SOURCE_HOST") == "10.0.0.1"

    def test_falls_back_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_src.INPUTS, "SOURCE_HOST", "")
        monkeypatch.setenv("SOURCE_HOST", "10.0.0.2")
        assert sm_src._env("SOURCE_HOST") == "10.0.0.2"

    def test_inputs_takes_priority_over_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_src.INPUTS, "SOURCE_HOST", "from_inputs")
        monkeypatch.setenv("SOURCE_HOST", "from_env")
        assert sm_src._env("SOURCE_HOST") == "from_inputs"

    def test_missing_required_key_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_src.INPUTS, "SOURCE_HOST", "")
        monkeypatch.delenv("SOURCE_HOST", raising=False)
        with pytest.raises(SystemExit):
            sm_src._env("SOURCE_HOST")

    def test_returns_default_when_not_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sm_src.INPUTS, "SOURCE_HOST", "")
        monkeypatch.delenv("SOURCE_HOST", raising=False)
        assert sm_src._env("SOURCE_HOST", default="fallback") == "fallback"


# ---------------------------------------------------------------------------
# _poll_job
# ---------------------------------------------------------------------------


class TestPollJob:
    def _make_client(self) -> MagicMock:
        return MagicMock(spec=OntapClient)

    def test_returns_when_state_not_running(self) -> None:
        client = self._make_client()
        client.get.return_value = {"state": "success", "message": "done"}
        result = sm_src._poll_job(client, "job-uuid-1")
        assert result["state"] == "success"

    def test_polls_until_non_running_state(self) -> None:
        client = self._make_client()
        client.get.side_effect = [
            {"state": "running"},
            {"state": "running"},
            {"state": "success"},
        ]
        with patch("snapmirror_provision_src_managed.time.sleep"):
            result = sm_src._poll_job(client, "job-uuid-1", interval=1)
        assert result["state"] == "success"
        assert client.get.call_count == 3

    def test_passes_correct_job_url(self) -> None:
        client = self._make_client()
        client.get.return_value = {"state": "success"}
        sm_src._poll_job(client, "abc-123")
        call_path = client.get.call_args[0][0]
        assert "abc-123" in call_path

    def test_returns_failure_state_without_raising(self) -> None:
        """_poll_job returns the failure record — callers decide what to do."""
        client = self._make_client()
        client.get.return_value = {"state": "failure", "error": {"message": "boom"}}
        result = sm_src._poll_job(client, "job-uuid-fail")
        assert result["state"] == "failure"


# ---------------------------------------------------------------------------
# _wait_snapmirrored
# ---------------------------------------------------------------------------


class TestWaitSnapmirrored:
    def _make_client(self) -> MagicMock:
        return MagicMock(spec=OntapClient)

    def test_returns_immediately_when_already_snapmirrored(self) -> None:
        client = self._make_client()
        client.get.return_value = {"state": "snapmirrored", "lag_time": "PT5M", "healthy": True}
        result = sm_src._wait_snapmirrored(client, "rel-uuid-1", interval=1, max_wait=60)
        assert result["state"] == "snapmirrored"
        assert client.get.call_count == 1

    def test_polls_until_snapmirrored(self) -> None:
        client = self._make_client()
        client.get.side_effect = [
            {"state": "transferring"},
            {"state": "transferring"},
            {"state": "snapmirrored"},
        ]
        with patch("snapmirror_provision_src_managed.time.sleep"):
            result = sm_src._wait_snapmirrored(client, "rel-uuid-1", interval=1, max_wait=600)
        assert result["state"] == "snapmirrored"

    def test_raises_timeout_if_never_snapmirrored(self) -> None:
        client = self._make_client()
        client.get.return_value = {"state": "transferring"}
        with patch("snapmirror_provision_src_managed.time.sleep"):
            with pytest.raises(RuntimeError, match="Timed out"):
                # max_wait=1, interval=2 → loop exits after first iteration
                sm_src._wait_snapmirrored(client, "rel-uuid-1", interval=2, max_wait=1)

    def test_queries_correct_relationship_url(self) -> None:
        client = self._make_client()
        client.get.return_value = {"state": "snapmirrored"}
        sm_src._wait_snapmirrored(client, "my-rel-uuid", interval=1, max_wait=60)
        call_path = client.get.call_args[0][0]
        assert "my-rel-uuid" in call_path
