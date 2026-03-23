"""HTTP step plugin — executes REST API calls."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from orchestrio.models import StepDefinition, StepResult, StepStatus
from orchestrio.plugins.base import StepPlugin

logger = logging.getLogger("orchestrio.http")


@StepPlugin.register("http")
class HttpPlugin(StepPlugin):
    """Execute an HTTP request defined in step config.

    Expected config keys:
        method     — HTTP method (default GET)
        url        — Target URL
        headers    — Optional dict of headers
        body       — Optional request body (dict → JSON, str → raw)
        timeout    — Seconds (default 30)
        verify_ssl — Verify TLS certificates (default true). Set to false
                     for self-signed / lab certificates.
        username   — Username for Basic auth (used with password)
        password   — Password for Basic auth (used with username)
        poll       — Optional polling block.  When present the request is
                     repeated on ``interval_seconds`` cadence until the
                     ``until`` condition is satisfied.  Each response is
                     printed to stdout (only when it changes from the
                     previous one).  Config shape:
                       poll:
                         interval_seconds: 10
                         until:
                           field: state          # dotted path in body
                           equals: success       # stop when equal  — OR —
                           not_equals: running   # stop when not equal

    Note: if both ``username``/``password`` and an explicit
    ``Authorization`` header are provided, the explicit header wins.
    """

    async def execute(
        self,
        step: StepDefinition,
        context: dict[str, Any],
    ) -> StepResult:
        cfg = step.config
        method = cfg.get("method", "GET").upper()
        url = cfg.get("url", "")
        headers: dict[str, str] = dict(cfg.get("headers", {}))
        body = cfg.get("body")
        timeout = cfg.get("timeout", 30)
        verify_ssl = cfg.get("verify_ssl", True)
        username = cfg.get("username")
        password = cfg.get("password")

        # Build Basic auth header from username/password if no explicit
        # Authorization header was supplied.
        if username is not None and "Authorization" not in headers:
            token = base64.b64encode(f"{username}:{password or ''}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        # ── Request logging (visible with -v / DEBUG level) ────────
        logger.debug("┌─ %s %s", method, url)
        # Log headers but redact Authorization value
        for k, v in headers.items():
            safe = "***" if k.lower() == "authorization" else v
            logger.debug("│  Header  %s: %s", k, safe)
        if body is not None:
            if isinstance(body, (dict, list)):
                logger.debug("│  Body    %s", json.dumps(body, indent=2))
            else:
                logger.debug("│  Body    %s", body)
        logger.debug("└─ timeout=%ss  verify_ssl=%s", timeout, verify_ssl)
        # ──────────────────────────────────────────────────────────

        poll_cfg = cfg.get("poll")
        started  = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(verify=verify_ssl) as client:
                if poll_cfg:
                    resp_body = await self._poll(
                        client, method, url, headers, body, timeout, poll_cfg
                    )
                    return StepResult(
                        name=step.name,
                        status=StepStatus.SUCCESS,
                        started_at=started,
                        finished_at=datetime.now(timezone.utc),
                        output={"body": resp_body},
                    )

                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, (dict, list)) else None,
                    content=body if isinstance(body, str) else None,
                    timeout=timeout,
                )

            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text

            logger.debug("   ← %s %s", response.status_code, response.reason_phrase)

            return StepResult(
                name=step.name,
                status=StepStatus.SUCCESS if response.is_success else StepStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                output={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": resp_body,
                },
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return StepResult(
                name=step.name,
                status=StepStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=str(exc),
            )

    # ── Polling helper ─────────────────────────────────────────────

    @staticmethod
    def _walk(obj: Any, dotted_path: str) -> Any:
        """Walk a dotted path through nested dicts/lists."""
        for key in dotted_path.split("."):
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return obj

    async def _poll(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        body: Any,
        timeout: int,
        poll_cfg: dict[str, Any],
    ) -> Any:
        """Repeat the request until the ``until`` condition is met.

        Prints each response to stdout, but only when it differs from
        the previous one (avoids flooding the console with identical lines).
        Returns the final response body so downstream steps can reference it.
        """
        interval: float = poll_cfg.get("interval_seconds", 10)
        until_cfg: dict[str, Any] = poll_cfg.get("until", {})
        field      = until_cfg.get("field", "")
        eq_val     = until_cfg.get("equals")
        neq_val    = until_cfg.get("not_equals")

        prev_text: str | None = None
        last_body: Any = {}

        while True:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                content=body if isinstance(body, str) else None,
                timeout=timeout,
            )

            try:
                resp_body = response.json()
                resp_text = json.dumps(resp_body)
            except Exception:
                resp_body = response.text
                resp_text = resp_body

            # Print only when the response changes
            if resp_text != prev_text:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if isinstance(resp_body, dict):
                    print(f"{ts}  [JOB] {json.dumps(resp_body, indent=2)}")
                else:
                    print(f"{ts}  [JOB] {resp_text}")
                prev_text = resp_text
                last_body = resp_body

            logger.debug("   ← %s (poll)", response.status_code)

            # Check exit condition
            current_val = self._walk(resp_body, field) if field else None
            done = False
            if eq_val is not None and current_val == eq_val:
                done = True
            elif neq_val is not None and current_val != neq_val:
                done = True

            if done:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                print(f"{ts}  ✓ Poll complete — {field}={current_val!r}")
                return last_body

            await asyncio.sleep(interval)
