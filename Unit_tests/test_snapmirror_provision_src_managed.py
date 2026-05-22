# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.
"""Unit tests for shared helpers in snapmirror_provision_src_managed."""

from __future__ import annotations

import pytest
import snapmirror_provision_src_managed as sm_src


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
