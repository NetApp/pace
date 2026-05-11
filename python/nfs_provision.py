#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

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

# -- Inputs (edit these directly, same as the YAML env: block) ----------------
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
# ---------------------------------------------------------------------------------


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


def main() -> None:
    args = parse_args()

    # Load env file first so its values can be read via os.environ below
    if args.env_file:
        _load_env_file(args.env_file)

    # Push ENV block values into os.environ so OntapClient.from_env() picks them up
    for key, value in ENV.items():
        if value and key not in os.environ:
            os.environ[key] = value

    # Resolve each value: CLI arg > env var > ENV block > built-in default (matches YAML priority)
    svm = args.svm or os.environ.get("SVM_NAME") or ENV["SVM_NAME"] or "vs0"
    volume = (
        args.volume or os.environ.get("VOLUME_NAME") or ENV["VOLUME_NAME"] or "vol_nfs_test_01"
    )
    size = args.size or os.environ.get("VOLUME_SIZE") or ENV["VOLUME_SIZE"] or "100MB"
    aggregate = args.aggregate or os.environ.get("AGGR_NAME") or ENV["AGGR_NAME"] or ""
    client_match = (
        args.client_match or os.environ.get("CLIENT_MATCH") or ENV["CLIENT_MATCH"] or "0.0.0.0/0"
    )

    if not aggregate:
        logger.error("--aggregate is required (or set AGGR_NAME in env / --env-file)")
        sys.exit(1)

    policy_name = f"{volume}_export_policy"

    with OntapClient.from_env() as client:
        # Step 1 - create volume (idempotent: skip if already exists)
        # POST /storage/volumes to create a new FlexVol with a NAS junction path.
        # Volume creation is asynchronous - the response contains a job UUID.
        existing_vol = client.get(
            "/storage/volumes",
            fields="name,uuid",
            name=volume,
            **{"svm.name": svm},
        )
        if existing_vol.get("records"):
            logger.info("Volume '%s' already exists - skipping create", volume)
        else:
            logger.info("Creating volume '%s' (%s) on SVM '%s'...", volume, size, svm)
            create_resp = client.post(
                "/storage/volumes",
                body={
                    "name": volume,
                    "svm": {"name": svm},
                    "aggregates": [{"name": aggregate}],
                    "size": size,
                    "nas": {"path": f"/{volume}"},
                },
            )

            # Step 2 - poll volume-creation job
            # Block until the async job finishes before proceeding.
            # poll_job raises RuntimeError if the job ends in a failure state.
            job_uuid = create_resp["job"]["uuid"]
            logger.info("Volume creation job: %s", job_uuid)
            client.poll_job(job_uuid)
            logger.info("Volume '%s' created successfully", volume)

        # Step 3 - fetch volume UUID
        # The UUID is required to PATCH the volume later when assigning the export policy.
        # Filter by name + svm.name to pinpoint exactly the volume just created.
        vol_resp = client.get(
            "/storage/volumes",
            fields="name,uuid",
            name=volume,
            **{"svm.name": svm},
        )
        if not vol_resp.get("records"):
            raise RuntimeError(f"Volume '{volume}' not found on SVM '{svm}' after creation")
        volume_uuid = vol_resp["records"][0]["uuid"]

        # Step 4 - create export policy (idempotent: skip if already exists)
        # Creates a dedicated policy named <volume>_export_policy scoped to the SVM.
        # A per-volume policy makes it easy to manage access rules independently.
        existing_policy = client.get(
            "/protocols/nfs/export-policies",
            fields="name,id",
            name=policy_name,
            **{"svm.name": svm},
        )
        if existing_policy.get("records"):
            logger.info("Export policy '%s' already exists - skipping create", policy_name)
        else:
            logger.info("Creating export policy '%s'...", policy_name)
            client.post(
                "/protocols/nfs/export-policies",
                body={"name": policy_name, "svm": {"name": svm}},
            )

        # Step 5 - fetch export policy ID
        # The numeric ID is required when POSTing rules to the policy.
        # Filter by name + svm.name to retrieve only this policy's record.
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
        policy_id = policy_resp["records"][0]["id"]

        # Step 6 - add client rule (idempotent: skip if a matching rule already exists)
        # POST a rule to the export policy allowing the given client IP or CIDR range.
        # ro_rule, rw_rule, superuser = 'any' is suitable for lab; tighten for production.
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
        else:
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

        # Step 7 - assign export policy to volume
        # PATCH the volume's nas.export_policy field to link the policy.
        # This makes the volume accessible to NFS clients that match the rule.
        logger.info("Assigning export policy to volume...")
        patch_resp = client.patch(
            f"/storage/volumes/{volume_uuid}",
            body={"nas": {"export_policy": {"name": policy_name}}},
        )

        # Step 8 - poll assign-policy job
        # The PATCH may return a job UUID if the operation is async.
        # Only poll if a UUID was returned; sync responses skip this block.
        if "job" in patch_resp:
            client.poll_job(patch_resp["job"]["uuid"])

        # Step 9 - print summary
        # Log a single success line with volume, size, SVM, mount path,
        # export policy name, and client rule for quick confirmation.
        logger.info(
            "[OK] Volume '%s' (%s) created on SVM '%s' | Mount path: /%s | "
            "Export policy '%s' created with client rule '%s' and assigned to volume",
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
