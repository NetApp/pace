#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Provision a CIFS (SMB) share on a NetApp storage cluster.

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
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from ontap_client import OntapApiError, OntapClient, load_env_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

ENV = {
    "ONTAP_HOST": "",  # cluster management IP — set via ONTAP_HOST env var
    "ONTAP_USER": "admin",
    "ONTAP_PASS": "",  # never hardcode — set via ONTAP_PASS env var
    "SVM_NAME": "vs0",
    "VOLUME_NAME": "volume",
    "VOLUME_SIZE": "100MB",
    "AGGR_NAME": "",  # required — set via --aggregate or AGGR_NAME env var
    "SHARE_NAME": "cifs_test",
    "SHARE_COMMENT": "Provisioned by PACE",
    "ACL_USER": "Everyone",
    "ACL_PERMISSION": "full_control",
    "CIFS_SERVER_NAME": "ONTAP-CIFS",
    "CIFS_WORKGROUP": "WORKGROUP",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision a CIFS share")
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


def _pick(cli_val: str | None, env_key: str, default: str = "") -> str:
    """Return the first non-empty value from: CLI arg, env var, ENV dict, or default."""
    return cli_val or os.environ.get(env_key) or ENV.get(env_key, "") or default


def _require(value: str, flag: str, env_key: str) -> str:
    """Return *value* or exit with a clear error if it is empty."""
    if not value:
        logger.error("--%s is required (or set %s in env / --env-file)", flag, env_key)
        sys.exit(1)
    return value


def _resolve_config(args: argparse.Namespace) -> tuple[dict[str, str], bool]:
    """Load env file and CLI args, then return (str_config, create_cifs_server).

    Returns a tuple of:
    - A ``dict[str, str]`` with all string config values.
    - A ``bool`` indicating whether to auto-create the CIFS server.
    """
    if args.env_file:
        load_env_file(args.env_file)

    for key, value in ENV.items():
        if value and key not in os.environ:
            os.environ[key] = value

    cfg: dict[str, str] = {
        "aggregate": _require(_pick(args.aggregate, "AGGR_NAME"), "aggregate", "AGGR_NAME"),
        "svm": _require(_pick(args.svm, "SVM_NAME"), "svm", "SVM_NAME"),
        "volume": _require(_pick(args.volume, "VOLUME_NAME"), "volume", "VOLUME_NAME"),
        "share_name": _require(_pick(args.share_name, "SHARE_NAME"), "share-name", "SHARE_NAME"),
        "size": _pick(args.size, "VOLUME_SIZE", "100MB"),
        "share_comment": _pick(args.share_comment, "SHARE_COMMENT", "Provisioned by PACE"),
        "acl_user": _pick(args.acl_user, "ACL_USER", "Everyone"),
        "acl_permission": _pick(args.acl_permission, "ACL_PERMISSION", "full_control"),
        "cifs_server_name": _pick(args.cifs_server_name, "CIFS_SERVER_NAME", "ONTAP-CIFS"),
        "workgroup": _pick(args.workgroup, "CIFS_WORKGROUP", "WORKGROUP"),
    }
    return cfg, bool(args.create_cifs_server)


def _ensure_cifs_server(
    client: OntapClient,
    svm: str,
    create_cifs_server: bool,
    cifs_server_name: str,
    workgroup: str,
) -> None:
    """Verify a CIFS server exists on the SVM, optionally creating one if missing."""
    cifs_svc_resp = client.get(
        "/protocols/cifs/services",
        fields="svm.name,enabled",
        **{"svm.name": svm},
    )
    if cifs_svc_resp.get("num_records", 0) > 0:
        logger.info("CIFS server confirmed on SVM '%s'", svm)
        return

    if not create_cifs_server:
        logger.error(
            "ABORTED - no CIFS server found on SVM '%s'. "
            "Pass --create-cifs-server to create one automatically, or use "
            "'vserver cifs create' before running this script.",
            svm,
        )
        sys.exit(1)

    logger.info(
        "No CIFS server on SVM '%s' - creating workgroup server '%s' in workgroup '%s'...",
        svm,
        cifs_server_name,
        workgroup,
    )
    resp = client.post(
        "/protocols/cifs/services",
        body={
            "svm": {"name": svm},
            "name": cifs_server_name,
            "workgroup": workgroup,
            "enabled": True,
        },
    )
    if resp.get("job"):
        client.poll_job(resp["job"]["uuid"])
    logger.info(
        "CIFS server '%s' created in workgroup '%s' on SVM '%s'",
        cifs_server_name,
        workgroup,
        svm,
    )


def _ensure_volume_ntfs(
    client: OntapClient, svm: str, volume: str, size: str, aggregate: str
) -> dict:
    """Create the FlexVol (NTFS security style) if it does not exist. Returns the job result."""
    existing = client.get(
        "/storage/volumes",
        fields="name,uuid",
        name=volume,
        **{"svm.name": svm},
    )
    if existing.get("records"):
        logger.info("Volume '%s' already exists - skipping create", volume)
        return {"state": "skipped", "message": "volume already existed"}

    logger.info("Creating volume '%s' (%s) on SVM '%s'...", volume, size, svm)
    resp = client.post(
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
    job_uuid = resp["job"]["uuid"]
    logger.info("Volume creation job: %s", job_uuid)
    return client.poll_job(job_uuid)


def _get_svm_uuid(client: OntapClient, svm: str) -> str:
    """Fetch and return the UUID for the named SVM."""
    resp = client.get("/svm/svms", fields="name,uuid", name=svm)
    return resp["records"][0]["uuid"]


def _ensure_cifs_share(
    client: OntapClient,
    svm_uuid: str,
    share_name: str,
    volume: str,
    svm: str,
    share_comment: str,
) -> None:
    """Create the CIFS share if it does not already exist."""
    try:
        existing = client.get(
            f"/protocols/cifs/shares/{svm_uuid}/{share_name}",
            fields="name",
        )
        share_exists = bool(existing.get("name"))
    except OntapApiError as exc:
        if exc.status_code == 404:
            share_exists = False
        else:
            raise

    if share_exists:
        logger.info("CIFS share '%s' already exists - skipping create", share_name)
        return

    logger.info("Creating CIFS share '%s' on path '/%s'...", share_name, volume)
    client.post(
        "/protocols/cifs/shares",
        body={
            "name": share_name,
            "path": f"/{volume}",
            "svm": {"name": svm},
            "comment": share_comment,
        },
    )


def _set_share_acl(
    client: OntapClient,
    svm_uuid: str,
    share_name: str,
    acl_user: str,
    acl_permission: str,
) -> None:
    """Patch the share ACL entry for the given user with the specified permission."""
    logger.info("Setting ACL: %s -> %s...", acl_user, acl_permission)
    client.patch(
        f"/protocols/cifs/shares/{svm_uuid}/{share_name}/acls/{acl_user}/windows",
        body={"permission": acl_permission},
    )


def _verify_and_log_acls(client: OntapClient, svm_uuid: str, share_name: str) -> None:
    """Fetch the share and log each ACL entry for confirmation."""
    logger.info("Verifying share '%s'...", share_name)
    resp = client.get(
        f"/protocols/cifs/shares/{svm_uuid}/{share_name}",
        fields="name,path,acls",
    )
    for acl in resp.get("acls", []):
        logger.info(
            "  ACL: %s (%s) -> %s",
            acl.get("user_or_group", "N/A"),
            acl.get("type", "N/A"),
            acl.get("permission", "N/A"),
        )


def main() -> None:
    """Resolve configuration, then orchestrate CIFS server, volume, share, and ACL setup."""
    cfg, create_cifs_server = _resolve_config(parse_args())
    svm = cfg["svm"]
    volume = cfg["volume"]
    size = cfg["size"]
    aggregate = cfg["aggregate"]
    share_name = cfg["share_name"]
    share_comment = cfg["share_comment"]
    acl_user = cfg["acl_user"]
    acl_permission = cfg["acl_permission"]

    with OntapClient.from_env() as client:
        _ensure_cifs_server(
            client, svm, create_cifs_server, cfg["cifs_server_name"], cfg["workgroup"]
        )

        job_result = _ensure_volume_ntfs(client, svm, volume, size, aggregate)
        state = job_result.get("state", "unknown")
        message = job_result.get("message", "")
        logger.info("Volume '%s' job -> %s: %s", volume, state, message)

        svm_uuid = _get_svm_uuid(client, svm)
        _ensure_cifs_share(client, svm_uuid, share_name, volume, svm, share_comment)
        _set_share_acl(client, svm_uuid, share_name, acl_user, acl_permission)
        _verify_and_log_acls(client, svm_uuid, share_name)

    logger.info(
        "[OK] CIFS share '%s' on volume '%s' (SVM: %s) | Path: /%s | ACL: %s -> %s",
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
