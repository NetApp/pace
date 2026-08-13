#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Retrieve storage cluster version, nodes, and aggregates.

Steps:
    1. GET /cluster          — cluster name, ONTAP version, contact, location
    2. GET /cluster/nodes    — list all nodes with serial numbers
    3. GET /storage/aggregates — list aggregates with state and used space

Prerequisites::

    pip install -r requirements.txt
    export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=secret

Usage::

    python cluster_info.py
"""

from __future__ import annotations

import logging
import sys

from ontap_client import OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Retrieve cluster version and print all node names with serial numbers."""
    with OntapClient.from_env() as client:
        # Step 1 — cluster version, contact, and location
        cluster = client.get("/cluster", fields="name,version,contact,location")
        logger.info(
            "Cluster: %s — ONTAP %s  contact=%s  location=%s",
            cluster.get("name", "unknown"),
            cluster.get("version", {}).get("full", "unknown"),
            cluster.get("contact", "—"),
            cluster.get("location", "—"),
        )

        # Step 2 — node list with serial numbers
        nodes_resp = client.get("/cluster/nodes", fields="name,serial_number")
        records = nodes_resp.get("records", [])
        logger.info("Nodes in cluster: %d", nodes_resp.get("num_records", len(records)))

        for node in records:
            logger.info(
                "  %-30s  serial: %s",
                node.get("name", "—"),
                node.get("serial_number", "—"),
            )

        # Step 3 — aggregate list with state and used space
        aggr_resp = client.get("/storage/aggregates", fields="name,state,space.block_storage")
        aggr_records = aggr_resp.get("records", [])
        logger.info("Aggregates in cluster: %d", aggr_resp.get("num_records", len(aggr_records)))

        for aggr in aggr_records:
            block = aggr.get("space", {}).get("block_storage", {})
            total = block.get("size", 0)
            used = block.get("used", 0)
            used_pct = (used / total * 100) if total else 0
            logger.info(
                "  %-30s  state: %-10s  used: %.1f%%",
                aggr.get("name", "—"),
                aggr.get("state", "—"),
                used_pct,
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("cluster_info failed")
        sys.exit(1)
