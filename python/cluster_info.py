#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Retrieve ONTAP cluster version and list all nodes with serial numbers.

Steps:
    1. GET /cluster - retrieve cluster name and ONTAP version
    2. GET /cluster/nodes - list all nodes with serial numbers

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
    with OntapClient.from_env() as client:
        # Step 1 - cluster version
        cluster = client.get("/cluster", fields="version")
        logger.info(
            "Cluster: %s - ONTAP %s",
            cluster.get("name", "unknown"),
            cluster.get("version", {}).get("full", "unknown"),
        )

        # Step 2 - node list with serial numbers
        nodes_resp = client.get("/cluster/nodes", fields="name,serial_number")
        records = nodes_resp.get("records", [])
        logger.info("Nodes in cluster: %d", nodes_resp.get("num_records", len(records)))

        for node in records:
            logger.info(
                "  %-30s  serial: %s",
                node.get("name", "-"),
                node.get("serial_number", "-"),
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("cluster_info failed")
        sys.exit(1)
