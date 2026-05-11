"""Unit tests for ontap_client.OntapClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from ontap_client import OntapApiError, OntapClient

# ---------------------------------------------------------------------------
# OntapApiError
# ---------------------------------------------------------------------------


class TestOntapApiError:
    def test_json_detail_stored(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 400
        resp.json.return_value = {"message": "Bad request", "code": "123"}
        err = OntapApiError(resp)
        assert err.status_code == 400
        assert err.detail == {"message": "Bad request", "code": "123"}
        assert "400" in str(err)

    def test_text_fallback_when_not_json(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 500
        resp.json.side_effect = ValueError("no JSON")
        resp.text = "Internal Server Error"
        err = OntapApiError(resp)
        assert err.detail == "Internal Server Error"
        assert "500" in str(err)

    def test_is_exception_subclass(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 404
        resp.json.return_value = {}
        assert isinstance(OntapApiError(resp), Exception)


# ---------------------------------------------------------------------------
# OntapClient.__init__
# ---------------------------------------------------------------------------


class TestOntapClientInit:
    def test_base_url_formed_correctly(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert client.base_url == "https://10.0.0.1/api"
        client.close()

    def test_session_auth_set(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "secret")
        assert client._session.auth == ("admin", "secret")
        client.close()

    def test_verify_ssl_defaults_false(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert client._session.verify is False
        client.close()

    def test_verify_ssl_can_be_enabled(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass", verify_ssl=True)
        assert client._session.verify is True
        client.close()

    def test_default_timeout_stored(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert client.timeout == 30
        client.close()

    def test_custom_timeout_stored(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass", timeout=60)
        assert client.timeout == 60
        client.close()

    def test_default_headers_include_accept(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert "application/hal+json" in client._session.headers.get("Accept", "")
        client.close()

    def test_default_headers_include_content_type(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert client._session.headers.get("Content-Type") == "application/json"
        client.close()


# ---------------------------------------------------------------------------
# OntapClient.from_env
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_missing_ontap_host_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONTAP_HOST", raising=False)
        monkeypatch.delenv("ONTAP_PASS", raising=False)
        with pytest.raises(SystemExit):
            OntapClient.from_env()

    def test_missing_ontap_pass_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONTAP_HOST", "10.0.0.1")
        monkeypatch.delenv("ONTAP_PASS", raising=False)
        with pytest.raises(SystemExit):
            OntapClient.from_env()

    def test_builds_client_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONTAP_HOST", "10.0.0.1")
        monkeypatch.setenv("ONTAP_PASS", "secret")
        monkeypatch.setenv("ONTAP_USER", "testuser")
        client = OntapClient.from_env()
        assert client.base_url == "https://10.0.0.1/api"
        assert client._session.auth == ("testuser", "secret")
        client.close()

    def test_default_user_is_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONTAP_HOST", "10.0.0.1")
        monkeypatch.setenv("ONTAP_PASS", "secret")
        monkeypatch.delenv("ONTAP_USER", raising=False)
        client = OntapClient.from_env()
        assert client._session.auth == ("admin", "secret")
        client.close()

    def test_verify_ssl_true_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONTAP_HOST", "10.0.0.1")
        monkeypatch.setenv("ONTAP_PASS", "secret")
        monkeypatch.setenv("ONTAP_VERIFY_SSL", "true")
        client = OntapClient.from_env()
        assert client._session.verify is True
        client.close()

    def test_verify_ssl_false_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONTAP_HOST", "10.0.0.1")
        monkeypatch.setenv("ONTAP_PASS", "secret")
        monkeypatch.delenv("ONTAP_VERIFY_SSL", raising=False)
        client = OntapClient.from_env()
        assert client._session.verify is False
        client.close()


# ---------------------------------------------------------------------------
# OntapClient._url
# ---------------------------------------------------------------------------


class TestUrl:
    def setup_method(self) -> None:
        self.client = OntapClient("10.0.0.1", "admin", "pass")

    def teardown_method(self) -> None:
        self.client.close()

    def test_absolute_path_prefixed_with_base(self) -> None:
        assert self.client._url("/cluster") == "https://10.0.0.1/api/cluster"

    def test_relative_path_prefixed_with_base(self) -> None:
        assert self.client._url("cluster/nodes") == "https://10.0.0.1/api/cluster/nodes"

    def test_absolute_https_url_returned_unchanged(self) -> None:
        url = "https://other.host/api/cluster"
        assert self.client._url(url) == url


# ---------------------------------------------------------------------------
# OntapClient._request
# ---------------------------------------------------------------------------


class TestRequest:
    def setup_method(self) -> None:
        self.client = OntapClient("10.0.0.1", "admin", "pass")
        self.mock_resp = MagicMock(spec=requests.Response)
        self.client._session.request = MagicMock(return_value=self.mock_resp)

    def teardown_method(self) -> None:
        self.client.close()

    def test_success_returns_json(self) -> None:
        self.mock_resp.ok = True
        self.mock_resp.status_code = 200
        self.mock_resp.content = b'{"name": "cluster1"}'
        self.mock_resp.json.return_value = {"name": "cluster1"}
        result = self.client._request("GET", "/cluster")
        assert result == {"name": "cluster1"}

    def test_204_returns_empty_dict(self) -> None:
        self.mock_resp.ok = True
        self.mock_resp.status_code = 204
        self.mock_resp.content = b""
        result = self.client._request("DELETE", "/some/resource")
        assert result == {}

    def test_empty_content_returns_empty_dict(self) -> None:
        self.mock_resp.ok = True
        self.mock_resp.status_code = 200
        self.mock_resp.content = b""
        result = self.client._request("GET", "/cluster")
        assert result == {}

    def test_non_ok_raises_ontap_api_error(self) -> None:
        self.mock_resp.ok = False
        self.mock_resp.status_code = 404
        self.mock_resp.json.return_value = {"message": "Not found"}
        with pytest.raises(OntapApiError) as exc_info:
            self.client._request("GET", "/missing")
        assert exc_info.value.status_code == 404

    def test_uses_default_timeout(self) -> None:
        self.mock_resp.ok = True
        self.mock_resp.status_code = 200
        self.mock_resp.content = b"{}"
        self.mock_resp.json.return_value = {}
        self.client._request("GET", "/cluster")
        call_kwargs = self.client._session.request.call_args[1]
        assert call_kwargs["timeout"] == self.client.timeout

    def test_url_built_from_path(self) -> None:
        self.mock_resp.ok = True
        self.mock_resp.status_code = 200
        self.mock_resp.content = b"{}"
        self.mock_resp.json.return_value = {}
        self.client._request("GET", "/cluster")
        call_args = self.client._session.request.call_args[0]
        assert call_args[1] == "https://10.0.0.1/api/cluster"


# ---------------------------------------------------------------------------
# OntapClient HTTP convenience methods
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_mock_session() -> OntapClient:
    client = OntapClient("10.0.0.1", "admin", "pass")
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.content = b'{"records": []}'
    mock_resp.json.return_value = {"records": []}
    client._session.request = MagicMock(return_value=mock_resp)
    yield client
    client.close()


class TestHttpMethods:
    def test_get_adds_fields_param(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.get("/cluster/nodes", fields="name,serial_number")
        params = client_with_mock_session._session.request.call_args[1]["params"]
        assert params["fields"] == "name,serial_number"

    def test_get_adds_default_return_timeout(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.get("/cluster/nodes")
        params = client_with_mock_session._session.request.call_args[1]["params"]
        assert params["return_timeout"] == "120"

    def test_get_no_fields_key_when_omitted(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.get("/cluster/nodes")
        params = client_with_mock_session._session.request.call_args[1]["params"]
        assert "fields" not in params

    def test_get_passes_extra_params(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.get("/cluster/nodes", membership="available")
        params = client_with_mock_session._session.request.call_args[1]["params"]
        assert params["membership"] == "available"

    def test_post_uses_post_method(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.post("/cluster", {"name": "c1"})
        method = client_with_mock_session._session.request.call_args[0][0]
        assert method == "POST"

    def test_post_sends_json_body(self, client_with_mock_session: OntapClient) -> None:
        body = {"name": "c1", "password": "secret"}
        client_with_mock_session.post("/cluster", body)
        json_arg = client_with_mock_session._session.request.call_args[1]["json"]
        assert json_arg == body

    def test_patch_uses_patch_method(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.patch("/cluster/nodes/uuid1", {"state": "up"})
        method = client_with_mock_session._session.request.call_args[0][0]
        assert method == "PATCH"

    def test_patch_sends_json_body(self, client_with_mock_session: OntapClient) -> None:
        body = {"state": "up"}
        client_with_mock_session.patch("/cluster/nodes/uuid1", body)
        json_arg = client_with_mock_session._session.request.call_args[1]["json"]
        assert json_arg == body

    def test_delete_uses_delete_method(self, client_with_mock_session: OntapClient) -> None:
        client_with_mock_session.delete("/volumes/uuid1")
        method = client_with_mock_session._session.request.call_args[0][0]
        assert method == "DELETE"


# ---------------------------------------------------------------------------
# OntapClient.poll_job
# ---------------------------------------------------------------------------

_JOB_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class TestPollJob:
    def setup_method(self) -> None:
        self.client = OntapClient("10.0.0.1", "admin", "pass")

    def teardown_method(self) -> None:
        self.client.close()

    def test_success_state_returns_job(self) -> None:
        self.client.get = MagicMock(return_value={"state": "success", "message": "done"})
        result = self.client.poll_job(_JOB_UUID)
        assert result["state"] == "success"

    def test_failure_state_raises_runtime_error(self) -> None:
        self.client.get = MagicMock(return_value={"state": "failure", "message": "boom"})
        with pytest.raises(RuntimeError, match="failed"):
            self.client.poll_job(_JOB_UUID)

    def test_failure_includes_job_message(self) -> None:
        self.client.get = MagicMock(return_value={"state": "failure", "message": "disk error"})
        with pytest.raises(RuntimeError, match="disk error"):
            self.client.poll_job(_JOB_UUID)

    def test_polls_until_success(self) -> None:
        responses = [
            {"state": "running"},
            {"state": "running"},
            {"state": "success"},
        ]
        self.client.get = MagicMock(side_effect=responses)
        with (
            patch("ontap_client.time.sleep"),
            patch("ontap_client.time.monotonic", return_value=0),
        ):
            result = self.client.poll_job(_JOB_UUID, interval=1, timeout=300)
        assert result["state"] == "success"
        assert self.client.get.call_count == 3

    def test_timeout_raises_timeout_error(self) -> None:
        self.client.get = MagicMock(return_value={"state": "running"})
        # First monotonic() → start time (0), second → past deadline (400)
        with (
            patch("ontap_client.time.sleep"),
            patch("ontap_client.time.monotonic", side_effect=[0, 400]),
        ):
            with pytest.raises(TimeoutError):
                self.client.poll_job(_JOB_UUID, interval=1, timeout=300)

    def test_connection_error_retries_then_succeeds(self) -> None:
        self.client.get = MagicMock(
            side_effect=[
                requests.exceptions.ConnectionError("disconnected"),
                {"state": "success"},
            ]
        )
        with (
            patch("ontap_client.time.sleep"),
            patch("ontap_client.time.monotonic", return_value=0),
        ):
            result = self.client.poll_job(_JOB_UUID, interval=1, timeout=300)
        assert result["state"] == "success"

    def test_connection_error_past_deadline_raises_timeout(self) -> None:
        self.client.get = MagicMock(
            side_effect=requests.exceptions.ConnectionError("disconnected")
        )
        # 1st monotonic → deadline start (0), 2nd → past deadline (400)
        with (
            patch("ontap_client.time.sleep"),
            patch("ontap_client.time.monotonic", side_effect=[0, 400]),
        ):
            with pytest.raises(TimeoutError):
                self.client.poll_job(_JOB_UUID, interval=1, timeout=300)

    def test_polls_correct_job_url(self) -> None:
        self.client.get = MagicMock(return_value={"state": "success"})
        self.client.poll_job(_JOB_UUID)
        call_args = self.client.get.call_args[0][0]
        assert _JOB_UUID in call_args


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_enter_returns_self(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        assert client.__enter__() is client
        client.close()

    def test_exit_closes_session(self) -> None:
        client = OntapClient("10.0.0.1", "admin", "pass")
        close_mock = MagicMock()
        client._session.close = close_mock
        with client:
            pass
        close_mock.assert_called_once()

    def test_with_statement_usage(self) -> None:
        """OntapClient can be used as a context manager without errors."""
        with OntapClient("10.0.0.1", "admin", "pass") as client:
            assert isinstance(client, OntapClient)
