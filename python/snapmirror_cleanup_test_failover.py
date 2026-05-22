# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""SnapMirror Test Failover Cleanup — deletes the FlexClone created by test_failover.

Finds the clone via SnapMirror relationship UUID tag ("<uuid>:test").
Only clones tagged by snapmirror_test_failover.py are touched — manually
created volumes are never matched or deleted.

Phases:
    0  Relationship-pick  — find SM relationship on correct cluster
    A  Tag-based find     — locate clone tagged with "<uuid>:test"
    B  SMAS removal       — delete any SMAS relationship on the clone (releases lock)
    C  Unmount            — remove NAS junction path (with retry)
    D  Offline            — set volume state to offline
    E  Delete             — delete the clone and confirm removal

Prerequisites:
    1. pip install -r requirements.txt
    2. ONTAP 9.8+ on both clusters
    3. snapmirror_test_failover.py must have been run first — this script
       only finds clones tagged by that script
    4. The SnapMirror relationship must still be accessible on one of the clusters
    5. Admin credentials for both clusters

Usage::

    export CLUSTER_A=10.x.x.x   CLUSTER_B=10.y.y.y
    export DEST_USER=admin       DEST_PASS=secret
    export SOURCE_VOLUME=vol_rw_01
    export SOURCE_SVM=vs0
    python snapmirror_cleanup_test_failover.py
"""

from __future__ import annotations

import logging
import os
import sys
import time

from ontap_client import OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USER INPUTS — fill in your values here before running
# ---------------------------------------------------------------------------
INPUTS = {
    "CLUSTER_A": "",  # first cluster management IP — set via CLUSTER_A env var
    "CLUSTER_B": "",  # second cluster management IP — set via CLUSTER_B env var
    "DEST_USER": "admin",
    "DEST_PASS": "",  # set via DEST_PASS env var — never hardcode
    "SOURCE_VOLUME": "",  # source volume name (e.g. vol_rw_01)
    "SOURCE_SVM": "",  # source SVM name
}
# ---------------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
    """Return the value for *key* from INPUTS or os.environ.

    Logs an error and exits if the resolved value is empty and no *default* is given.
    """
    val = INPUTS.get(key) or os.environ.get(key, default)
    if not val:
        logger.error(
            "Input '%s' is required — set it in the INPUTS block at the top of this file",
            key,
        )
        sys.exit(1)
    return val


def _pick_cluster_by_relationship(
    cluster_a: str,
    cluster_b: str,
    user: str,
    passwd: str,
    source_svm: str,
    source_volume: str,
) -> tuple[str, dict]:
    """Return (cluster_ip, relationship_record) for the cluster that owns this SM rel."""
    source_path = f"{source_svm}:{source_volume}"
    for host in (cluster_a, cluster_b):
        try:
            with OntapClient(host, user, passwd, verify_ssl=False, timeout=20) as client:
                resp = client.get(
                    "/snapmirror/relationships",
                    fields="uuid,source.path,destination.path,state,healthy",
                    **{"source.path": source_path, "max_records": "1"},
                )
            if resp.get("num_records", 0) >= 1:
                return host, resp["records"][0]
        except Exception as exc:
            logger.warning("  cluster %s — %s", host, exc)

    logger.error(
        "No SM relationship found for %s on either cluster (%s, %s)",
        source_path,
        cluster_a,
        cluster_b,
    )
    sys.exit(1)


def _find_tagged_clone(client: OntapClient, rel_uuid: str) -> dict | None:
    """Return a dict with uuid/name/svm for the clone tagged '<rel_uuid>:test', or None."""
    resp = client.get(
        "/storage/volumes",
        fields="name,uuid,svm.name,state,nas.path",
        **{"_tags": f"{rel_uuid}:test", "max_records": "1"},
    )
    if resp.get("num_records", 0) == 0:
        return None
    rec = resp["records"][0]
    return {
        "uuid": rec.get("uuid", ""),
        "name": rec.get("name", ""),
        "svm": rec.get("svm", {}).get("name", ""),
    }


def _remove_smas_and_bring_online(
    client: OntapClient, clone_uuid: str, clone_svm: str, clone_name: str
) -> None:
    """Delete any SMAS relationship on the clone, then ensure the volume is online."""
    logger.info("=== Phase B: Remove SMAS relationship on clone (if any) ===")
    smas_resp = client.get(
        "/snapmirror/relationships",
        fields="uuid,state",
        **{
            "destination.path": f"{clone_svm}:{clone_name}",
            "max_records": "10",
        },
    )
    for smas_rel in smas_resp.get("records", []):
        smas_uuid = smas_rel.get("uuid", "")
        logger.info("  Deleting SMAS relationship %s on clone", smas_uuid)
        try:
            resp = client.delete(
                f"/snapmirror/relationships/{smas_uuid}?return_timeout=120&force=true"
            )
            job_uuid = resp.get("job", {}).get("uuid")
            if job_uuid:
                client.poll_job(job_uuid)
        except Exception as exc:
            logger.warning("delete_smas_rel %s — %s (continuing)", smas_uuid, exc)
    if smas_resp.get("num_records", 0) == 0:
        logger.info("  No SMAS relationships found on clone — continuing")
    try:
        resp = client.patch(
            f"/storage/volumes/{clone_uuid}?return_timeout=120",
            body={"state": "online"},
        )
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            client.poll_job(job_uuid)
    except Exception as exc:
        logger.warning("bring_online — %s (continuing)", exc)


def _unmount_clone(client: OntapClient, clone_uuid: str) -> None:
    """Remove the NAS junction path; retries up to 6 times before aborting."""
    logger.info("=== Phase C: Unmount clone ===")
    for attempt in range(1, 7):
        try:
            resp = client.patch(
                f"/storage/volumes/{clone_uuid}?return_timeout=120",
                body={"nas": {"path": ""}},
            )
            job_uuid = resp.get("job", {}).get("uuid")
            if job_uuid:
                client.poll_job(job_uuid)
            return
        except Exception as exc:
            logger.warning("unmount_clone attempt %d/6 — %s", attempt, exc)
            if attempt < 6:
                time.sleep(10)
    logger.error("Failed to unmount clone after 6 attempts — aborting")
    sys.exit(1)


def _offline_clone(client: OntapClient, clone_uuid: str) -> None:
    """Set the volume state to offline (required before delete)."""
    logger.info("=== Phase D: Offline clone ===")
    try:
        resp = client.patch(
            f"/storage/volumes/{clone_uuid}?return_timeout=120",
            body={"state": "offline"},
        )
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            client.poll_job(job_uuid)
    except Exception as exc:
        logger.warning("offline_clone — %s", exc)


def _delete_and_confirm_clone(
    client: OntapClient, clone_uuid: str, clone_name: str, dest_host: str
) -> None:
    """Delete the clone volume and confirm it is gone."""
    logger.info("=== Phase E: Delete clone ===")
    try:
        resp = client.delete(f"/storage/volumes/{clone_uuid}?return_timeout=120")
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            client.poll_job(job_uuid)
    except Exception as exc:
        logger.warning("delete_clone — %s", exc)
    confirm = client.get(
        "/storage/volumes",
        fields="name,uuid",
        **{"uuid": clone_uuid, "max_records": "1"},
    )
    if confirm.get("num_records", 0) == 0:
        logger.info(
            "=== CLEANUP COMPLETE — clone '%s' deleted from cluster %s ===",
            clone_name,
            dest_host,
        )
    else:
        logger.error("Clone '%s' still exists after delete attempt", clone_name)
        sys.exit(1)


def main() -> None:
    """Find the tagged FlexClone from a test failover and delete it through all cleanup phases."""
    cluster_a = _env("CLUSTER_A")
    cluster_b = _env("CLUSTER_B")
    dest_user = _env("DEST_USER")
    dest_pass = _env("DEST_PASS")
    source_volume = _env("SOURCE_VOLUME")
    source_svm = _env("SOURCE_SVM")

    logger.info("=== Phase 0: Find SnapMirror relationship ===")
    dest_host, rel = _pick_cluster_by_relationship(
        cluster_a,
        cluster_b,
        dest_user,
        dest_pass,
        source_svm,
        source_volume,
    )
    rel_uuid = rel.get("uuid", "")
    logger.info(
        "RELATIONSHIP FOUND | cluster=%s | uuid=%s | source=%s | dest=%s | state=%s | healthy=%s",
        dest_host,
        rel_uuid,
        rel.get("source", {}).get("path"),
        rel.get("destination", {}).get("path"),
        rel.get("state"),
        rel.get("healthy"),
    )

    if rel.get("state") != "snapmirrored":
        logger.warning(
            "Relationship state=%s healthy=%s — proceeding with cleanup anyway",
            rel.get("state"),
            rel.get("healthy"),
        )

    with OntapClient(dest_host, dest_user, dest_pass, verify_ssl=False) as client:
        logger.info("=== Phase A: Find tagged clone ===")
        clone = _find_tagged_clone(client, rel_uuid)
        if clone is None:
            logger.info(
                "NO TAGGED CLONE FOUND for %s:%s on %s — nothing to clean up",
                source_svm,
                source_volume,
                dest_host,
            )
            return

        logger.info(
            "CLONE FOUND | name=%s | uuid=%s | svm=%s | cluster=%s",
            clone["name"],
            clone["uuid"],
            clone["svm"],
            dest_host,
        )
        _remove_smas_and_bring_online(client, clone["uuid"], clone["svm"], clone["name"])
        _unmount_clone(client, clone["uuid"])
        _offline_clone(client, clone["uuid"])
        _delete_and_confirm_clone(client, clone["uuid"], clone["name"], dest_host)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("snapmirror_cleanup_test_failover failed")
        sys.exit(1)
