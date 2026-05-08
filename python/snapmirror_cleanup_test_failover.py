#!/usr/bin/env python3
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
    "CLUSTER_A": "",  # first cluster management IP — never hardcode
    "CLUSTER_B": "",  # second cluster management IP — never hardcode
    "DEST_USER": "admin",
    "DEST_PASS": "",  # set via DEST_PASS env var
    "SOURCE_VOLUME": "",  # source volume name (e.g. vol_rw_01)
    "SOURCE_SVM": "vs0",  # source SVM name
}
# ---------------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
    """Return the value for *key* from the INPUTS dict, falling back to the environment.

    Exits with an error log if the resolved value is empty and *default* is not set.
    """
    # Prefer value from INPUTS dict; fall back to environment variable.
    val = INPUTS.get(key) or os.environ.get(key, default)
    if not val:
        logger.error(
            "Input '%s' is required — set it in the INPUTS block at the top of this file",
            key,
        )
        sys.exit(1)
    return val


def _poll_job(client: OntapClient, job_uuid: str, interval: int = 10) -> dict:
    """Poll an ONTAP async job until it leaves the 'running' state.

    Returns the final job record. Callers should inspect the returned state/error fields.
    """
    while True:
        result = client.get(f"/cluster/jobs/{job_uuid}", fields="state,message,error,code")
        state = result.get("state", "unknown")
        logger.info("  job %s — state=%s", job_uuid, state)
        if state != "running":
            return result
        time.sleep(interval)


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
            client = OntapClient(host, user, passwd, verify_ssl=False, timeout=20)
            resp = client.get(
                "/snapmirror/relationships",
                fields="uuid,source.path,destination.path,state,healthy",
                **{"source.path": source_path, "max_records": "1"},
            )
            client.close()
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


def _find_tagged_clone(
    client: OntapClient, rel_uuid: str, source_svm: str, source_volume: str, dest_host: str
) -> dict | None:
    """Phase A: Find the FlexClone tagged '<rel_uuid>:test'.

    Returns the volume record if found, or None if no tagged clone exists.
    Only clones tagged by snapmirror_test_failover.py are matched.
    """
    logger.info("=== Phase A: Find tagged clone ===")
    resp = client.get(
        "/storage/volumes",
        fields="name,uuid,svm.name,state,nas.path",
        **{"_tags": f"{rel_uuid}:test", "max_records": "1"},
    )
    if resp.get("num_records", 0) == 0:
        logger.info(
            "NO TAGGED CLONE FOUND for %s:%s on %s — nothing to clean up",
            source_svm,
            source_volume,
            dest_host,
        )
        return None
    clone = resp["records"][0]
    logger.info(
        "CLONE FOUND | name=%s | uuid=%s | svm=%s | cluster=%s",
        clone.get("name"),
        clone.get("uuid"),
        clone.get("svm", {}).get("name"),
        dest_host,
    )
    return clone


def _remove_smas_and_restore_online(
    client: OntapClient, clone_uuid: str, clone_svm: str, clone_name: str
) -> None:
    """Phase B: Delete any SMAS relationships on the clone and bring it online.

    A SnapMirror Active Sync relationship on the clone holds an internal ONTAP
    job lock that prevents unmount and delete (errors 917536, 23003209).
    Deleting it first releases the lock. The volume is also brought online in
    case a previous failed cleanup run left it in an offline state.
    """
    logger.info("=== Phase B: Remove SMAS relationship on clone (if any) ===")
    smas_resp = client.get(
        "/snapmirror/relationships",
        fields="uuid,state",
        **{"destination.path": f"{clone_svm}:{clone_name}", "max_records": "10"},
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
                _poll_job(client, job_uuid)
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
            _poll_job(client, job_uuid)
    except Exception as exc:
        logger.warning("bring_online — %s (continuing)", exc)


def _unmount_clone(client: OntapClient, clone_uuid: str) -> None:
    """Phase C: Remove NAS junction path to unmount the clone.

    Retries up to 6 times with a 10-second delay to allow ONTAP to fully
    release background locks before giving up.
    """
    logger.info("=== Phase C: Unmount clone ===")
    for attempt in range(1, 7):
        try:
            resp = client.patch(
                f"/storage/volumes/{clone_uuid}?return_timeout=120",
                body={"nas": {"path": ""}},
            )
            job_uuid = resp.get("job", {}).get("uuid")
            if job_uuid:
                _poll_job(client, job_uuid)
            return
        except Exception as exc:
            logger.warning("unmount_clone attempt %d/6 — %s", attempt, exc)
            if attempt < 6:
                time.sleep(10)
    logger.error("Failed to unmount clone after 6 attempts — aborting")
    sys.exit(1)


def _offline_clone(client: OntapClient, clone_uuid: str) -> None:
    """Phase D: Set volume state to offline.

    A volume must be offline before it can be deleted in ONTAP.
    """
    logger.info("=== Phase D: Offline clone ===")
    try:
        resp = client.patch(
            f"/storage/volumes/{clone_uuid}?return_timeout=120",
            body={"state": "offline"},
        )
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            _poll_job(client, job_uuid)
    except Exception as exc:
        logger.warning("offline_clone — %s", exc)


def _delete_clone_and_verify(
    client: OntapClient, clone_uuid: str, clone_name: str, dest_host: str
) -> None:
    """Phase E: Delete the clone and verify it no longer exists.

    Treats a 'not found' response as success (idempotent).
    """
    logger.info("=== Phase E: Delete clone ===")
    try:
        resp = client.delete(f"/storage/volumes/{clone_uuid}?return_timeout=120")
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            _poll_job(client, job_uuid)
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


def _find_relationship(
    cluster_a: str,
    cluster_b: str,
    dest_user: str,
    dest_pass: str,
    source_svm: str,
    source_volume: str,
) -> tuple[str, dict, str]:
    """Phase 0: Locate the SnapMirror relationship on the correct cluster.

    Searches both clusters and returns (dest_host, rel, rel_uuid) for the
    cluster that owns the destination side of the relationship.
    Logs a warning if the relationship is not in 'snapmirrored' state.
    """
    logger.info("=== Phase 0: Find SnapMirror relationship ===")
    dest_host, rel = _pick_cluster_by_relationship(
        cluster_a, cluster_b, dest_user, dest_pass, source_svm, source_volume
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
    return dest_host, rel, rel_uuid


def main() -> None:
    """Delete the test-failover FlexClone and restore the SnapMirror relationship.

    Identifies the correct cluster via the SnapMirror relationship UUID, then
    removes SMAS entries, unmounts, offlines, and deletes the FlexClone.
    """
    cluster_a = _env("CLUSTER_A")
    cluster_b = _env("CLUSTER_B")
    dest_user = _env("DEST_USER")
    dest_pass = _env("DEST_PASS")
    source_volume = _env("SOURCE_VOLUME")
    source_svm = _env("SOURCE_SVM")

    dest_host, rel, rel_uuid = _find_relationship(
        cluster_a, cluster_b, dest_user, dest_pass, source_svm, source_volume
    )

    with OntapClient(dest_host, dest_user, dest_pass, verify_ssl=False) as client:
        clone = _find_tagged_clone(client, rel_uuid, source_svm, source_volume, dest_host)
        if clone is None:
            return

        clone_uuid = clone.get("uuid", "")
        clone_name = clone.get("name", "")
        clone_svm = clone.get("svm", {}).get("name", "")

        _remove_smas_and_restore_online(client, clone_uuid, clone_svm, clone_name)
        _unmount_clone(client, clone_uuid)
        _offline_clone(client, clone_uuid)
        _delete_clone_and_verify(client, clone_uuid, clone_name, dest_host)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("snapmirror_cleanup_test_failover failed")
        sys.exit(1)
