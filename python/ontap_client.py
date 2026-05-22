# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Lightweight ONTAP REST API client for use across example scripts.

Usage::

    from ontap_client import OntapClient

    with OntapClient.from_env() as client:
        cluster = client.get("/cluster", fields="version")
        print(cluster["name"], cluster["version"]["full"])
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

import requests
import urllib3

logger = logging.getLogger("ontap_client")

__all__ = ["OntapClient", "OntapApiError", "load_env_file"]

# All examples in this repo disable SSL verification to support environments
# that use self-signed certificates.  We recommend setting
# ONTAP_VERIFY_SSL=true once CA-signed certificates are in place.  The
# warning suppression below keeps script output readable when verification
# is disabled.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_DEFAULT_TIMEOUT = 90
_DEFAULT_HEADERS = {
    "Accept": "application/hal+json",
    "Content-Type": "application/json",
    "X-Dot-Client-App": "pace-example",
}


class OntapApiError(Exception):
    """Raised when an ONTAP REST call returns a non-success status."""

    def __init__(self, response: requests.Response) -> None:
        self.status_code = response.status_code
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        super().__init__(f"HTTP {self.status_code}: {detail}")
        self.detail = detail


class OntapClient:
    """Thin wrapper around :mod:`requests` for ONTAP REST API calls.

    Parameters
    ----------
    host:
        Cluster management LIF hostname or IP.
    username:
        ONTAP admin user.
    password:
        ONTAP admin password.
    verify_ssl:
        Defaults to ``False`` to support self-signed certificates.
        Set to ``True`` once CA-signed certificates are in place.
    timeout:
        Default request timeout in seconds.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = False,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = f"https://{host}/api"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.verify = verify_ssl
        self._session.headers.update(_DEFAULT_HEADERS)

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> OntapClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def update_auth(self, username: str, password: str) -> None:
        """Replace the HTTP Basic-Auth credentials on the underlying session.

        Use this when the cluster switches authentication context mid-workflow
        (e.g. after ``POST /cluster`` when the node moves from pre-cluster mode
        to full cluster mode and requires the new cluster admin password).
        """
        self._session.auth = (username, password)

    # -- Factory ------------------------------------------------------------

    @classmethod
    def from_env(cls) -> OntapClient:
        """Build a client from standard ``ONTAP_*`` environment variables.

        Required environment variables:
            ``ONTAP_HOST``, ``ONTAP_PASS``

        Optional (with defaults):
            ``ONTAP_USER`` (default ``admin``),
            ``ONTAP_VERIFY_SSL`` (default ``false``)
        """
        host = os.environ.get("ONTAP_HOST", "")
        if not host:
            logger.error("ONTAP_HOST environment variable is required")
            sys.exit(1)
        password = os.environ.get("ONTAP_PASS", "")
        if not password:
            logger.error("ONTAP_PASS environment variable is required")
            sys.exit(1)

        return cls(
            host=host,
            username=os.environ.get("ONTAP_USER", "admin"),
            password=password,
            verify_ssl=os.environ.get("ONTAP_VERIFY_SSL", "false").lower() == "true",
        )

    # -- HTTP helpers -------------------------------------------------------

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("timeout", self.timeout)
        url = self._url(path)
        logger.debug("%s %s", method, url)

        try:
            resp = self._session.request(method, url, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"{method} {url} timed out after {kwargs['timeout']} s — "
                "the cluster may be busy or unreachable. "
                "Increase the timeout via OntapClient(..., timeout=<seconds>) if needed."
            ) from exc

        if not resp.ok:
            raise OntapApiError(resp)

        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def get(self, path: str, *, fields: str = "", **params: str) -> dict[str, Any]:
        if fields:
            params["fields"] = fields
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=body)

    def patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", path, json=body)

    def delete(self, path: str) -> dict[str, Any]:
        return self._request("DELETE", path)

    # -- Convenience --------------------------------------------------------

    def poll_job(
        self,
        job_uuid: str,
        *,
        interval: int = 5,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Poll an async job until it leaves the ``running`` state.

        Raises :class:`OntapApiError` if the job ends in ``failure``.
        Retries on transient connection errors (e.g. RemoteDisconnected).
        """
        url = f"/cluster/jobs/{job_uuid}"
        deadline = time.monotonic() + timeout

        while True:
            try:
                job = self.get(url, fields="state,message")
            except requests.exceptions.ConnectionError as exc:
                if time.monotonic() + interval > deadline:
                    raise TimeoutError(
                        f"Job {job_uuid} poll timed out after connection error: {exc}"
                    ) from exc
                logger.warning(
                    "Job %s — connection error during poll, retrying: %s", job_uuid, exc
                )
                time.sleep(interval)
                continue

            state = job.get("state", "unknown")
            logger.info("Job %s — state: %s", job_uuid, state)

            if state == "success":
                return job
            if state == "failure":
                msg = job.get("message", "no details")
                raise RuntimeError(f"Job {job_uuid} failed: {msg}")
            if time.monotonic() + interval > deadline:
                raise TimeoutError(f"Job {job_uuid} did not complete within {timeout}s")

            time.sleep(interval)

    def wait_snapmirrored(
        self,
        rel_uuid: str,
        *,
        interval: int = 15,
        max_wait: int = 1800,
    ) -> dict[str, Any]:
        """Poll a SnapMirror relationship until its state becomes ``snapmirrored``.

        Args:
            rel_uuid: UUID of the SnapMirror relationship to watch.
            interval:  Seconds between polls (default 15).
            max_wait:  Maximum total seconds to wait before raising (default 1800).

        Returns:
            The final relationship record when state == ``snapmirrored``.

        Raises:
            :class:`RuntimeError` if ``max_wait`` is exceeded.
        """
        elapsed = 0
        while elapsed < max_wait:
            result = self.get(
                f"/snapmirror/relationships/{rel_uuid}",
                fields="state,lag_time,healthy",
            )
            state = result.get("state", "unknown")
            logger.info("Relationship %s — state: %s", rel_uuid, state)
            if state == "snapmirrored":
                return result
            time.sleep(interval)
            elapsed += interval
        raise RuntimeError(f"Timed out waiting for relationship {rel_uuid} to reach snapmirrored")


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def load_env_file(path: str) -> None:
    """Load ``KEY=VALUE`` pairs from a file into :data:`os.environ` (dotenv style).

    Rules:
    - Blank lines and lines starting with ``#`` are ignored.
    - Values are set via :func:`os.environ.setdefault` so existing env vars
      take precedence.
    - Surrounding single or double quotes on values are stripped.

    Args:
        path: Path to the env file.  The script exits with an error message if
              the file does not exist or contains a malformed line.
    """
    from pathlib import Path  # local import to avoid top-level dependency

    p = Path(path)
    if not p.is_file():
        logger.error("Env file not found: %s", path)
        import sys

        sys.exit(1)
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.error("Env file %s line %d: expected KEY=VALUE, got: %s", path, lineno, line)
            import sys

            sys.exit(1)
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
