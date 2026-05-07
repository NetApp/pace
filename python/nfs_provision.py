#!/usr/bin/env python3
"""Create an ONTAP NFS volume with a dedicated export policy.

Steps:
    1. Create a FlexVol volume
    2. Poll the volume-creation job
    3. Fetch the new volume UUID
    4. Create a dedicated NFS export policy
    5. Fetch the new export policy ID
    6. Add a client-match rule to the policy
    7. Assign the policy to the volume
    8. Poll the assign-policy job
    9. Print summary

Usage::

    export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=secret
    python nfs_provision.py \\
        --svm vs0 \\
        --volume vol_nfs_test_01 \\
        --size 100MB \\
        --aggregate aggr1 \\
        --client-match 0.0.0.0/0

    # Or supply all values via an env file (same as YAML --env-file):
    python nfs_provision.py --env-file nfs-provision.env

Default values (vs0, vol_nfs_test_01, 0.0.0.0/0, etc.) are for illustration
only.  Replace them with values appropriate for your environment -
in particular, restrict ``--client-match`` to your actual client subnet.

This script is *not* idempotent: running it twice with the same volume name
will fail.  See ``python/README.md`` -> "Adapting for Your Environment" for
guidance on adding existence checks.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ontap_client import OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# Inputs (edit these directly, same as the YAML env: block)
# These are the defaults. CLI args and env vars override them.
ENV = {
    "ONTAP_HOST": "",  # cluster management IP - set here or via ONTAP_HOST env var
    "ONTAP_USER": "admin",
    "ONTAP_PASS": "",  # never hardcode - set via ONTAP_PASS env var
    "SVM_NAME": "vs1",
    "VOLUME_NAME": "vol_001",
    "VOLUME_SIZE": "100MB",
    "AGGR_NAME": "",  # required - set via --aggregate or AGGR_NAME env var
    "CLIENT_MATCH": "0.0.0.0/0",
}


def _load_env_file(path: str) -> None:
    """Load KEY=VALUE pairs from an env file into os.environ (dotenv style)."""
    p = Path(path)
    if not p.is_file():
        logger.error("Env file not found: %s", path)
        sys.exit(1)
    for lineno, raw in enumerate(p.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.error("Env file %s line %d: expected KEY=VALUE, got: %s", path, lineno, line)
            sys.exit(1)
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision an NFS volume on ONTAP")
    p.add_argument(
        "--env-file",
        "-E",
        metavar="FILE",
        help="Path to a KEY=VALUE env file (same format as orchestrio --env-file)",
    )
    p.add_argument("--svm", default=None)
    p.add_argument("--volume", default=None)
    p.add_argument("--size", default=None)
    p.add_argument("--aggregate", default=None)
    p.add_argument("--client-match", default=None)
    return p.parse_args()


def _resolve_config(args: argparse.Namespace) -> dict[str, str]:
    """Load env file and CLI args, then return the resolved configuration dict."""
    if args.env_file:
        _load_env_file(args.env_file)

    for key, value in ENV.items():
        if value and key not in os.environ:
            os.environ[key] = value

    aggregate = args.aggregate or os.environ.get("AGGR_NAME") or ENV["AGGR_NAME"] or ""
    if not aggregate:
        logger.error("--aggregate is required (or set AGGR_NAME in env / --env-file)")
        sys.exit(1)

    return {
        "svm": args.svm or os.environ.get("SVM_NAME") or ENV["SVM_NAME"] or "vs0",
        "volume": (
            args.volume or os.environ.get("VOLUME_NAME") or ENV["VOLUME_NAME"] or "vol_nfs_test_01"
        ),
        "size": args.size or os.environ.get("VOLUME_SIZE") or ENV["VOLUME_SIZE"] or "100MB",
        "aggregate": aggregate,
        "client_match": (
            args.client_match
            or os.environ.get("CLIENT_MATCH")
            or ENV["CLIENT_MATCH"]
            or "0.0.0.0/0"
        ),
    }


def _ensure_volume(client: OntapClient, svm: str, volume: str, size: str, aggregate: str) -> str:
    """Create the FlexVol if it does not exist. Returns the volume UUID."""
    existing = client.get(
        "/storage/volumes",
        fields="name,uuid",
        name=volume,
        **{"svm.name": svm},
    )
    if existing.get("records"):
        logger.info("Volume '%s' already exists - skipping create", volume)
    else:
        logger.info("Creating volume '%s' (%s) on SVM '%s'...", volume, size, svm)
        resp = client.post(
            "/storage/volumes",
            body={
                "name": volume,
                "svm": {"name": svm},
                "aggregates": [{"name": aggregate}],
                "size": size,
                "nas": {"path": f"/{volume}"},
            },
        )
        job_uuid = resp["job"]["uuid"]
        logger.info("Volume creation job: %s", job_uuid)
        client.poll_job(job_uuid)
        logger.info("Volume '%s' created successfully", volume)

    vol_resp = client.get(
        "/storage/volumes",
        fields="name,uuid",
        name=volume,
        **{"svm.name": svm},
    )
    if not vol_resp.get("records"):
        raise RuntimeError(f"Volume '{volume}' not found on SVM '{svm}' after creation")
    return vol_resp["records"][0]["uuid"]


def _ensure_export_policy(client: OntapClient, svm: str, policy_name: str) -> int:
    """Create the NFS export policy if it does not exist. Returns the policy ID."""
    existing = client.get(
        "/protocols/nfs/export-policies",
        fields="name,id",
        name=policy_name,
        **{"svm.name": svm},
    )
    if existing.get("records"):
        logger.info("Export policy '%s' already exists - skipping create", policy_name)
    else:
        logger.info("Creating export policy '%s'...", policy_name)
        client.post(
            "/protocols/nfs/export-policies",
            body={"name": policy_name, "svm": {"name": svm}},
        )

    policy_resp = client.get(
        "/protocols/nfs/export-policies",
        fields="name,id",
        name=policy_name,
        **{"svm.name": svm},
    )
    if not policy_resp.get("records"):
        raise RuntimeError(
            f"Export policy '{policy_name}' not found on SVM '{svm}' after creation"
        )
    return policy_resp["records"][0]["id"]


def _ensure_client_rule(client: OntapClient, policy_id: int, client_match: str) -> None:
    """Add a client-match rule to the export policy if one does not already exist."""
    existing_rules = client.get(
        f"/protocols/nfs/export-policies/{policy_id}/rules",
        fields="index,clients",
    )
    rule_exists = any(
        any(c.get("match") == client_match for c in r.get("clients", []))
        for r in existing_rules.get("records", [])
    )
    if rule_exists:
        logger.info("Client rule '%s' already exists in policy - skipping", client_match)
        return
    logger.info("Adding client rule '%s' to policy...", client_match)
    client.post(
        f"/protocols/nfs/export-policies/{policy_id}/rules",
        body={
            "clients": [{"match": client_match}],
            "ro_rule": ["any"],
            "rw_rule": ["any"],
            "superuser": ["any"],
        },
    )


def _assign_export_policy(client: OntapClient, volume_uuid: str, policy_name: str) -> None:
    """Assign the export policy to the volume and wait for any async job to complete."""
    logger.info("Assigning export policy to volume...")
    patch_resp = client.patch(
        f"/storage/volumes/{volume_uuid}",
        body={"nas": {"export_policy": {"name": policy_name}}},
    )
    if "job" in patch_resp:
        client.poll_job(patch_resp["job"]["uuid"])


def main() -> None:
    cfg = _resolve_config(parse_args())
    svm = cfg["svm"]
    volume = cfg["volume"]
    size = cfg["size"]
    aggregate = cfg["aggregate"]
    client_match = cfg["client_match"]
    policy_name = f"{volume}_export_policy"

    with OntapClient.from_env() as client:
        volume_uuid = _ensure_volume(client, svm, volume, size, aggregate)
        policy_id = _ensure_export_policy(client, svm, policy_name)
        _ensure_client_rule(client, policy_id, client_match)
        _assign_export_policy(client, volume_uuid, policy_name)

    logger.info(
        "[OK] Volume '%s' (%s) on SVM '%s' | Mount: /%s | "
        "Export policy '%s' with client rule '%s' assigned",
        volume,
        size,
        svm,
        volume,
        policy_name,
        client_match,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("nfs_provision failed")
        sys.exit(1)
