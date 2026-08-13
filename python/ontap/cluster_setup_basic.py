#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.
"""Create a storage cluster from two pre-cluster nodes (ONTAP 9 unified).
Steps:
    1. discover_nodes   — GET /api/cluster/nodes  (membership=available, retry 3x/30s)
    2. discover_local   — isolate the local node   (has management_interfaces != null)
    3. discover_partner — isolate the partner node (exclude local node UUID)
    4. create_cluster   — POST /api/cluster
    5. track_job        — poll job until state != running

Usage::

    # env vars directly
    export ONTAP_HOST=10.x.x.x   # pre-cluster node IP
    export ONTAP_USER=admin       # usually admin, empty pass on pre-cluster nodes
    export ONTAP_PASS=
    export CLUSTER_NAME=mycluster
    export CLUSTER_PASS=<your-password>
    export CLUSTER_MGMT_IP=10.x.x.x
    export CLUSTER_NETMASK=255.255.192.0
    export CLUSTER_GATEWAY=10.x.x.1
    export PARTNER_MGMT_IP=10.x.x.y
    python cluster_setup_basic.py

"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from ontap_client import OntapClient, load_env_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USER INPUTS — fill in your values here before running
# ---------------------------------------------------------------------------
INPUTS = {
    "ONTAP_HOST": "",  # Node 1 management IP — set via ONTAP_HOST env var
    "ONTAP_USER": "admin",
    "ONTAP_PASS": "",  # leave empty for pre-cluster nodes
    "CLUSTER_NAME": "cluster1",  # set via CLUSTER_NAME env var
    "CLUSTER_PASS": "",  # set via CLUSTER_PASS env var — choose your cluster admin password
    "CLUSTER_MGMT_IP": "",  # cluster management IP — set via CLUSTER_MGMT_IP env var
    "CLUSTER_NETMASK": "",  # set via CLUSTER_NETMASK env var
    "CLUSTER_GATEWAY": "",  # default gateway — set via CLUSTER_GATEWAY env var
    "PARTNER_MGMT_IP": "",  # Node 2 management IP — set via PARTNER_MGMT_IP env var
}
# ---------------------------------------------------------------------------

# ONTAP 9 unified — node discovery fields
_NODE_FIELDS = (
    "name,model,state,ha,version,serial_number,membership,"
    "cluster_interfaces,management_interfaces,metrocluster"
)


def _env(key: str, required: bool = True) -> str:
    """Return the value for *key* from INPUTS or os.environ.

    Logs an error and exits if *required* is True and the value is empty.
    """
    val = INPUTS.get(key) or os.environ.get(key, "")
    if required and not val:
        logger.error(
            "Input '%s' is required — set it in the INPUTS block at the top of this file",
            key,
        )
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _get_nodes(client: OntapClient, **kwargs) -> dict:
    """GET /cluster/nodes with the standard ONTAP 9 unified field set."""
    return client.get("/cluster/nodes", fields=_NODE_FIELDS, **kwargs)


def discover_nodes(client: OntapClient, attempts: int = 3, delay: int = 30) -> dict:  # type: ignore[return]
    """Step 1 — discover available nodes, retry up to 3 times."""
    for attempt in range(1, attempts + 1):
        try:
            result = _get_nodes(client, membership="available")
            logger.info("discover_nodes — %d node(s) found", result.get("num_records", 0))
            return result
        except Exception as exc:
            if attempt < attempts:
                logger.warning(
                    "discover_nodes failed (attempt %d/%d), retrying in %ds — %s",
                    attempt,
                    attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                raise RuntimeError(f"discover_nodes failed after {attempts} attempts") from exc


def discover_local(client: OntapClient) -> dict:
    """Step 2 — isolate the local node (management_interfaces != null)."""
    result = _get_nodes(
        client,
        membership="available",
        **{"management_interfaces": "!null"},
    )
    records = result.get("records", [])
    if not records:
        raise RuntimeError("discover_local: no local node returned")
    logger.info("discover_local  — %s", records[0]["name"])
    return result


def discover_partner(client: OntapClient, local_uuid: str) -> dict:
    """Step 3 — isolate the partner node (exclude local UUID)."""
    result = _get_nodes(
        client,
        membership="available",
        **{"uuid": f"!{local_uuid}"},
    )
    records = result.get("records", [])
    if not records:
        raise RuntimeError("discover_partner: no partner node returned")
    logger.info("discover_partner — %s", records[0]["name"])
    return result


def create_cluster(client: OntapClient, local: dict, partner: dict) -> dict:
    """Step 4 — POST /api/cluster to create the cluster."""
    cluster_name = _env("CLUSTER_NAME")
    cluster_pass = _env("CLUSTER_PASS")
    cluster_mgmt_ip = _env("CLUSTER_MGMT_IP")
    cluster_netmask = _env("CLUSTER_NETMASK")
    cluster_gateway = _env("CLUSTER_GATEWAY")
    ontap_host = _env("ONTAP_HOST")
    partner_mgmt_ip = _env("PARTNER_MGMT_IP")

    local_node = local["records"][0]
    partner_node = partner["records"][0]

    body = {
        "name": cluster_name,
        "password": cluster_pass,
        "management_interface": {
            "ip": {
                "address": cluster_mgmt_ip,
                "netmask": cluster_netmask,
                "gateway": cluster_gateway,
            }
        },
        "nodes": [
            {
                "name": f"{cluster_name}-01",
                "management_interface": {"ip": {"address": ontap_host}},
                "cluster_interface": {
                    "ip": {"address": local_node["cluster_interfaces"][0]["ip"]["address"]}
                },
            },
            {
                "name": f"{cluster_name}-02",
                "management_interface": {"ip": {"address": partner_mgmt_ip}},
                "cluster_interface": {
                    "ip": {"address": partner_node["cluster_interfaces"][0]["ip"]["address"]}
                },
            },
        ],
        "name_servers": {},
        "ntp_servers": {},
        "dns_domains": {},
        "configuration_backup": {},
    }

    result = client.post("/cluster?keep_precluster_config=true", body)
    job_uuid = result.get("job", {}).get("uuid")
    logger.info("create_cluster  — job %s", job_uuid)
    return result


def track_job(client: OntapClient, job_uuid: str) -> dict:
    """Step 5 — switch to cluster credentials then poll the job until completion.

    After ``POST /cluster`` the node transitions to full cluster mode and
    requires the new cluster-admin password.  Authentication is updated via
    :meth:`~ontap_client.OntapClient.update_auth` before polling begins.
    """
    # After cluster creation the node switches to cluster mode — use CLUSTER_PASS
    client.update_auth(_env("ONTAP_USER"), _env("CLUSTER_PASS"))
    return client.poll_job(job_uuid, interval=10, timeout=1800)


def main() -> None:
    """Orchestrate all five cluster-setup steps and log the resulting cluster URL."""
    host = _env("ONTAP_HOST")
    user = _env("ONTAP_USER")
    passwd = os.environ.get("ONTAP_PASS", "")  # empty on pre-cluster nodes

    logger.info("Cluster setup starting — connecting to %s", host)

    with OntapClient(host, user, passwd, verify_ssl=False, timeout=150) as client:
        discover_nodes(client)
        local = discover_local(client)
        partner = discover_partner(client, local["records"][0]["uuid"])
        job = create_cluster(client, local, partner)
        track_job(client, job["job"]["uuid"])

    cluster_name = _env("CLUSTER_NAME")
    cluster_mgmt_ip = _env("CLUSTER_MGMT_IP")
    logger.info(
        "Cluster '%s' created — UI: https://%s  login: %s / %s",
        cluster_name,
        cluster_mgmt_ip,
        _env("ONTAP_USER"),
        _env("CLUSTER_PASS"),
    )


def _load_env_file(path: str) -> None:
    """Load KEY=VALUE pairs from a .env file into both os.environ and the INPUTS dict."""
    load_env_file(path)
    for key in list(INPUTS):
        if val := os.environ.get(key):
            INPUTS[key] = val


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create an ONTAP cluster from two pre-cluster nodes."
    )
    parser.add_argument(
        "--env-file",
        metavar="FILE",
        help="Path to a .env file with KEY=VALUE pairs (one per build, like -ir in ha_create.exp).",
    )
    args = parser.parse_args()

    if args.env_file:
        _load_env_file(args.env_file)

    for key in list(INPUTS):
        val = os.environ.get(key)
        if val:
            INPUTS[key] = val

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("cluster_setup_basic failed")
        sys.exit(1)
