#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Provision a CIFS (SMB) share on ONTAP.

Steps:
    0. Pre-flight — verify CIFS server is enabled on the SVM
    1. Create a FlexVol volume (NTFS security style)
    2. Poll the volume-creation job
    3. Print volume creation status
    4. Create a CIFS share on the volume
    5. Fetch the SVM UUID (needed for ACL URL)
    6. Set the share ACL (PATCH existing Everyone entry)
    7. Verify the share and ACL
    8. Print summary

Usage::

    python cifs_provision.py

    # Or override values via CLI args:
    python cifs_provision.py --svm vs0 --volume cifs_test_env --aggregate aggr1

    # Or supply all values via an env file (same as YAML --env-file):
    python cifs_provision.py --env-file cifs-provision.env
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ontap_client import OntapApiError, OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Inputs (edit these directly, same as the YAML env: block) ────────────────
# These are the defaults. CLI args and env vars override them.
ENV = {
    "ONTAP_HOST": "",  # cluster management IP — set here or via ONTAP_HOST env var
    "ONTAP_USER": "admin",
    "ONTAP_PASS": "",  # never hardcode — set via ONTAP_PASS env var
    "SVM_NAME": "vs1",
    "VOLUME_NAME": "vol_002",
    "VOLUME_SIZE": "100MB",
    "AGGR_NAME": "sti232_vsim_sr091o_aggr1",  # required — set via --aggregate or AGGR_NAME env var
    "CLIENT_MATCH": "0.0.0.0/0",  # required — set via --client-match or CLIENT_MATCH env var
    "SHARE_NAME": "cifs_share_demo",
    "SHARE_COMMENT": "Provisioned by orchestrio",
    "ACL_USER": "Everyone",
    "ACL_PERMISSION": "full_control",
    "CIFS_SERVER_NAME": "ONTAP-CIFS",
    "CIFS_WORKGROUP": "WORKGROUP",
}
# ─────────────────────────────────────────────────────────────────────────────


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
    p = argparse.ArgumentParser(description="Provision a CIFS share on ONTAP")
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
    p.add_argument("--share-name", default=None)
    p.add_argument(
        "--share-comment",
        default=None,
    )
    p.add_argument("--acl-user", default=None)
    p.add_argument("--acl-permission", default=None)
    p.add_argument(
        "--create-cifs-server",
        action="store_true",
        help="Create a workgroup CIFS server on the SVM if none exists (uses --cifs-server-name / --workgroup)",
    )
    p.add_argument(
        "--cifs-server-name",
        default=None,
        help="NetBIOS name for the new CIFS server (max 15 chars, used with --create-cifs-server)",
    )
    p.add_argument(
        "--workgroup",
        default=None,
        help="Workgroup name for the new CIFS server (used with --create-cifs-server)",
    )
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
    volume = args.volume or os.environ.get("VOLUME_NAME") or ENV["VOLUME_NAME"] or "cifs_test_env"
    size = args.size or os.environ.get("VOLUME_SIZE") or ENV["VOLUME_SIZE"] or "100MB"
    aggregate = args.aggregate or os.environ.get("AGGR_NAME") or ENV["AGGR_NAME"] or ""
    share_name = (
        args.share_name or os.environ.get("SHARE_NAME") or ENV["SHARE_NAME"] or "cifs_share_demo"
    )
    share_comment = (
        args.share_comment
        or os.environ.get("SHARE_COMMENT")
        or ENV["SHARE_COMMENT"]
        or "Provisioned by orchestrio"
    )
    acl_user = args.acl_user or os.environ.get("ACL_USER") or ENV["ACL_USER"] or "Everyone"
    acl_permission = (
        args.acl_permission
        or os.environ.get("ACL_PERMISSION")
        or ENV["ACL_PERMISSION"]
        or "full_control"
    )

    create_cifs_server = args.create_cifs_server
    cifs_server_name = (
        args.cifs_server_name
        or os.environ.get("CIFS_SERVER_NAME")
        or ENV["CIFS_SERVER_NAME"]
        or "ONTAP-CIFS"
    )
    workgroup = (
        args.workgroup or os.environ.get("CIFS_WORKGROUP") or ENV["CIFS_WORKGROUP"] or "WORKGROUP"
    )

    if not aggregate:
        logger.error("--aggregate is required (or set AGGR_NAME in env / --env-file)")
        sys.exit(1)

    with OntapClient.from_env() as client:
        # Pre-flight — verify CIFS server is enabled on the SVM
        # A CIFS share cannot be created if no CIFS server exists on the SVM.
        # Exits early with a clear error rather than failing mid-workflow.
        cifs_svc_resp = client.get(
            "/protocols/cifs/services",
            fields="svm.name,enabled",
            **{"svm.name": svm},
        )
        if cifs_svc_resp.get("num_records", 0) == 0:
            if not create_cifs_server:
                logger.error(
                    "ABORTED — no CIFS server found on SVM '%s'. "
                    "Pass --create-cifs-server to create one automatically, or use "
                    "'vserver cifs create' before running this script.",
                    svm,
                )
                sys.exit(1)
            logger.info(
                "No CIFS server on SVM '%s' — creating workgroup server '%s' in workgroup '%s'…",
                svm,
                cifs_server_name,
                workgroup,
            )
            cifs_create_resp = client.post(
                "/protocols/cifs/services",
                body={
                    "svm": {"name": svm},
                    "name": cifs_server_name,
                    "workgroup": workgroup,
                    "enabled": True,
                },
            )
            # ONTAP may return an async job for CIFS server creation
            if cifs_create_resp.get("job"):
                cifs_job_uuid = cifs_create_resp["job"]["uuid"]
                logger.info("CIFS server creation job: %s", cifs_job_uuid)
                client.poll_job(cifs_job_uuid)
            logger.info(
                "CIFS server '%s' created in workgroup '%s' on SVM '%s'",
                cifs_server_name,
                workgroup,
                svm,
            )
        else:
            logger.info("CIFS server confirmed on SVM '%s'", svm)

        # Step 1 — create volume with NTFS security style (idempotent: skip if exists)
        # POST /storage/volumes to create a FlexVol with security_style=ntfs.
        # NTFS security style is required for CIFS/SMB share ACL enforcement.
        existing_vol = client.get(
            "/storage/volumes",
            fields="name,uuid",
            name=volume,
            **{"svm.name": svm},
        )
        if existing_vol.get("records"):
            logger.info("Volume '%s' already exists — skipping create", volume)
            job_result = {"state": "skipped", "message": "volume already existed"}
        else:
            logger.info("Creating volume '%s' (%s) on SVM '%s'…", volume, size, svm)
            create_resp = client.post(
                "/storage/volumes",
                body={
                    "name": volume,
                    "svm": {"name": svm},
                    "aggregates": [{"name": aggregate}],
                    "size": size,
                    "nas": {
                        "security_style": "ntfs",
                        "path": f"/{volume}",
                    },
                },
            )

            # Step 2 — poll volume-creation job
            # Block until the async job finishes; the job result is logged in Step 3.
            job_uuid = create_resp["job"]["uuid"]
            logger.info("Volume creation job: %s", job_uuid)
            job_result = client.poll_job(job_uuid)

        # Step 3 — print volume creation status
        # Log the final job state and message for confirmation before continuing.
        state = job_result.get("state", "unknown")
        message = job_result.get("message", "")
        logger.info("Volume '%s' job → %s: %s", volume, state, message)

        # Step 4 — create CIFS share (idempotent: skip if already exists)
        # POST /protocols/cifs/shares to create the share pointing at the volume junction.
        # ONTAP auto-creates a default 'Everyone / Full Control' ACL entry on creation.
        svm_resp = client.get(
            "/svm/svms",
            fields="name,uuid",
            name=svm,
        )
        svm_uuid = svm_resp["records"][0]["uuid"]

        try:
            existing_share = client.get(
                f"/protocols/cifs/shares/{svm_uuid}/{share_name}",
                fields="name",
            )
            share_exists = bool(existing_share.get("name"))
        except OntapApiError as exc:
            if exc.status_code == 404:
                share_exists = False
            else:
                raise
        if share_exists:
            logger.info("CIFS share '%s' already exists — skipping create", share_name)
        else:
            logger.info("Creating CIFS share '%s' on path '/%s'…", share_name, volume)
            client.post(
                "/protocols/cifs/shares",
                body={
                    "name": share_name,
                    "path": f"/{volume}",
                    "svm": {"name": svm},
                    "comment": share_comment,
                },
            )

        # Step 6 — set share ACL (PATCH the auto-created Everyone entry)
        # svm_uuid was resolved in Step 4 above (needed for the ACL URL).
        # PATCH replaces the permission on the existing ACL entry for the given user.
        # Default is 'Everyone' with 'full_control'; customise via ACL_USER/ACL_PERMISSION.
        logger.info("Setting ACL: %s → %s…", acl_user, acl_permission)
        client.patch(
            f"/protocols/cifs/shares/{svm_uuid}/{share_name}/acls/{acl_user}/windows",
            body={"permission": acl_permission},
        )

        # Step 7 — verify share and ACL
        # GET the share and inspect the acls array to confirm the permission was applied.
        # Logs each ACL entry (user, type, permission) for visual confirmation.
        logger.info("Verifying share '%s'…", share_name)
        verify_resp = client.get(
            f"/protocols/cifs/shares/{svm_uuid}/{share_name}",
            fields="name,path,acls",
        )
        acls = verify_resp.get("acls", [])
        for acl in acls:
            logger.info(
                "  ACL: %s (%s) → %s",
                acl.get("user_or_group", "—"),
                acl.get("type", "—"),
                acl.get("permission", "—"),
            )

        # Step 8 — print summary
        # Log a single success line with share name, volume, SVM, path, and ACL.
        logger.info(
            "✓ CIFS share '%s' created on volume '%s' (SVM: %s) | Path: /%s | ACL: %s → %s",
            share_name,
            volume,
            svm,
            volume,
            acl_user,
            acl_permission,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("cifs_provision failed")
        sys.exit(1)
