# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.
"""Unit tests for shared helpers in snapmirror_provision_dest_managed."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import snapmirror_provision_dest_managed as sm_dst
from ontap_client import OntapClient


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
            "records": [{"ip": {"address": "10.0.0.11"}, "services": ["data-nfs"]}]
        }
        assert sm_dst._get_ic_lif_ips(client) == []

    def test_returns_empty_on_empty_records(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"records": []}
        assert sm_dst._get_ic_lif_ips(client) == []

    def test_skips_records_with_no_ip_address(self) -> None:
        client = MagicMock(spec=OntapClient)
        client.get.return_value = {"records": [{"ip": {}, "services": ["intercluster-core"]}]}
        assert sm_dst._get_ic_lif_ips(client) == []


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
        sm_dst._check_ic_lif_preconditions(src, dst, ["10.0.0.1"], ["10.0.0.2"])

    def test_warns_when_different_subnets(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        src = MagicMock(spec=OntapClient)
        dst = MagicMock(spec=OntapClient)
        with caplog.at_level(logging.WARNING, logger="snapmirror_provision_dest_managed"):
            sm_dst._check_ic_lif_preconditions(src, dst, ["10.0.0.1"], ["192.168.1.1"])
        assert any("subnet" in msg.lower() for msg in caplog.messages)
