# Copyright 2026 NetApp, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Structured JSONL run logger for post-mortem debugging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

_REDACT_KEYS = frozenset({"authorization", "password", "token", "secret"})
_REDACTED = "***"


def _redact(obj: Any) -> Any:
    """Deep-copy *obj*, replacing values whose keys look sensitive."""
    if isinstance(obj, dict):
        return {k: _REDACTED if k.lower() in _REDACT_KEYS else _redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


class RunLogger:
    """Append-only JSONL writer that records workflow execution events.

    Each line is a self-contained JSON object with at least ``ts``,
    ``event``, and ``run_id``.  Designed for ``jq`` / grep workflows
    and log-aggregation pipelines.

    Use as a context manager so the file is flushed and closed cleanly::

        with RunLogger(path, run_id) as log:
            log.event("workflow_start", name="my_wf")
    """

    def __init__(self, path: str | Path, run_id: str) -> None:
        self._path = Path(path)
        self._run_id = run_id
        self._fh: TextIO | None = None

    def __enter__(self) -> RunLogger:
        self._fh = self._path.open("a", encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._fh and not self._fh.closed:
            self._fh.close()

    @property
    def path(self) -> Path:
        return self._path

    def event(self, event_type: str, **payload: Any) -> None:
        """Write a single event line.  Values are redacted automatically."""
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "run_id": self._run_id,
        }
        record.update(_redact(payload))
        line = json.dumps(record, default=str)
        if self._fh and not self._fh.closed:
            self._fh.write(line + "\n")
            self._fh.flush()


class NullRunLogger(RunLogger):
    """Drop-in replacement that discards all events (no file I/O)."""

    def __init__(self) -> None:
        self._path = Path("/dev/null")
        self._run_id = ""
        self._fh = None

    def __enter__(self) -> NullRunLogger:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def event(self, event_type: str, **payload: Any) -> None:
        pass
