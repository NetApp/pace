#!/usr/bin/env python3
"""Create an ONTAP NFS volume with a dedicated export policy.

Equivalent to:  orchestrio run yaml-workflows/workflows/nfs-provision.yaml

Steps:
    1. Create a FlexVol volume
    2. Poll the volume-creation job
    3. Fetch the new volume UUID
    4. Create a dedicated NFS export policy
    5. Add a client-match rule to the policy
    6. Assign the policy to the volume
    7. Poll the assign-policy job

Usage::

    export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=secret
    python nfs_provision.py \\
        --svm vs0 \\
        --volume vol_nfs_test_01 \\
        --size 100MB \\
        --aggregate aggr1 \\
        --client-match 0.0.0.0/0
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from ontap_client import OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision an NFS volume on ONTAP")
    p.add_argument("--svm", default=os.environ.get("SVM_NAME", "vs0"))
    p.add_argument("--volume", default=os.environ.get("VOLUME_NAME", "vol_nfs_test_01"))
    p.add_argument("--size", default=os.environ.get("VOLUME_SIZE", "100MB"))
    p.add_argument("--aggregate", default=os.environ.get("AGGR_NAME", ""))
    p.add_argument(
        "--client-match", default=os.environ.get("CLIENT_MATCH", "0.0.0.0/0")
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.aggregate:
        logger.error("--aggregate is required (or set AGGR_NAME env var)")
        sys.exit(1)

    policy_name = f"{args.volume}_export_policy"

    with OntapClient.from_env() as client:
        # Step 1 — create volume
        logger.info(
            "Creating volume '%s' (%s) on SVM '%s'…", args.volume, args.size, args.svm
        )
        create_resp = client.post(
            "/storage/volumes",
            body={
                "name": args.volume,
                "svm": {"name": args.svm},
                "aggregates": [{"name": args.aggregate}],
                "size": args.size,
                "nas": {"path": f"/{args.volume}"},
            },
        )

        # Step 2 — poll volume-creation job
        job_uuid = create_resp["job"]["uuid"]
        logger.info("Volume creation job: %s", job_uuid)
        client.poll_job(job_uuid)
        logger.info("Volume '%s' created successfully", args.volume)

        # Step 3 — fetch volume UUID
        vol_resp = client.get(
            "/storage/volumes",
            fields="name,uuid",
            name=args.volume,
            **{"svm.name": args.svm},
        )
        volume_uuid = vol_resp["records"][0]["uuid"]

        # Step 4 — create export policy
        logger.info("Creating export policy '%s'…", policy_name)
        client.post(
            "/protocols/nfs/export-policies",
            body={"name": policy_name, "svm": {"name": args.svm}},
        )

        # Step 5 — fetch export policy ID
        policy_resp = client.get(
            "/protocols/nfs/export-policies",
            fields="name,id",
            name=policy_name,
            **{"svm.name": args.svm},
        )
        policy_id = policy_resp["records"][0]["id"]

        # Step 6 — add client rule
        logger.info("Adding client rule '%s' to policy…", args.client_match)
        client.post(
            f"/protocols/nfs/export-policies/{policy_id}/rules",
            body={
                "clients": [{"match": args.client_match}],
                "ro_rule": ["any"],
                "rw_rule": ["any"],
                "superuser": ["any"],
            },
        )

        # Step 7 — assign export policy to volume
        logger.info("Assigning export policy to volume…")
        patch_resp = client.patch(
            f"/storage/volumes/{volume_uuid}",
            body={"nas": {"export_policy": {"name": policy_name}}},
        )

        # Step 8 — poll assign-policy job
        if "job" in patch_resp:
            client.poll_job(patch_resp["job"]["uuid"])

        logger.info(
            "Done — volume '%s' (%s) on SVM '%s', mount path: /%s, "
            "export policy '%s' with client rule '%s'",
            args.volume,
            args.size,
            args.svm,
            args.volume,
            policy_name,
            args.client_match,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("nfs_provision failed")
        sys.exit(1)
