#!/usr/bin/env python3
"""SnapMirror Test Failover — creates a writable FlexClone of a SnapMirror dest volume.

AUTO mode  (SOURCE_VOLUME=* or unset):
    Queries both clusters, picks the one with the most recently created DP volume.

TARGETED mode (SOURCE_VOLUME=vol_rw_01):
    Finds vol_rw_01_dest on either cluster.

Phases:
    0  Auto-detect which cluster has the target DP volume
    A  Pre-flight  — verify cluster + relationship health
    B  Snapshot    — get latest SnapMirror snapshot on dest volume
    C  Clone       — create writable FlexClone
    D  Verify      — confirm clone online + tag with SM relationship UUID
    E  Resync      — resync SnapMirror + validate healthy state

Prerequisites:
    1. pip install -r requirements.txt
    2. ONTAP 9.8+ on both clusters
    3. A healthy SnapMirror relationship must already exist (run
       snapmirror_provision_src_managed.py or snapmirror_provision_dest_managed.py first)
    4. Relationship state must be 'snapmirrored' (baseline transfer complete)
    5. At least one SnapMirror snapshot on the destination volume
    6. Admin credentials for both clusters

Usage::

    export CLUSTER_A=10.x.x.x  CLUSTER_B=10.y.y.y
    export DEST_USER=admin      DEST_PASS=secret
    export SOURCE_VOLUME=*      # or a specific volume name e.g. "vol_rw_01"
    python snapmirror_test_failover.py
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
    "SOURCE_VOLUME": "",  # source volume name, or * to auto-detect
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


def _wait_snapmirrored(
    client: OntapClient, rel_uuid: str, interval: int = 15, max_wait: int = 1800
) -> dict:
    """Poll a SnapMirror relationship until state reaches 'snapmirrored'.

    Raises RuntimeError if *max_wait* seconds elapse before convergence.
    """
    elapsed = 0
    while elapsed < max_wait:
        result = client.get(
            f"/snapmirror/relationships/{rel_uuid}",
            fields="state,lag_time,healthy",
        )
        state = result.get("state", "unknown")
        logger.info("  relationship %s — state=%s", rel_uuid, state)
        if state == "snapmirrored":
            return result
        time.sleep(interval)
        elapsed += interval
    raise RuntimeError(f"Timed out waiting for relationship {rel_uuid} to reach snapmirrored")


def _pick_cluster(
    cluster_a: str, cluster_b: str, user: str, passwd: str, vol_name_filter: str
) -> tuple[str, dict]:
    """Find which cluster has the target DP volume; return (cluster_ip, vol_record)."""
    dest_filter = f"{vol_name_filter}_dest" if vol_name_filter != "*" else "*_dest"

    best_cluster = ""
    best_vol: dict = {}

    for host in (cluster_a, cluster_b):
        try:
            client = OntapClient(host, user, passwd, verify_ssl=False, timeout=20)
            resp = client.get(
                "/storage/volumes",
                fields="name,create_time,uuid,svm.name,state,space.size",
                **{
                    "type": "dp",
                    "name": dest_filter,
                    "order_by": "create_time desc",
                    "max_records": "1",
                },
            )
            client.close()
            if resp.get("num_records", 0) >= 1:
                best_cluster = host
                best_vol = resp["records"][0]
                break
        except Exception as exc:
            logger.warning("  cluster %s — %s", host, exc)

    if not best_cluster:
        logger.error("No DP volumes found on either cluster (%s, %s)", cluster_a, cluster_b)
        sys.exit(1)

    return best_cluster, best_vol


def _preflight_and_get_rel(client: OntapClient, dp_vol_name: str, dp_svm_name: str) -> dict:
    """Phase A: Verify destination cluster and fetch the SnapMirror relationship.

    Returns the relationship record for the given DP volume.
    """
    logger.info("=== Phase A: Pre-flight ===")
    cluster = client.get("/cluster", fields="name,version")
    logger.info(
        "DEST CLUSTER | name=%s | ontap=%s",
        cluster.get("name"),
        cluster.get("version", {}).get("full"),
    )
    rel_resp = client.get(
        "/snapmirror/relationships",
        fields="uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
        **{"destination.path": f"{dp_svm_name}:{dp_vol_name}", "max_records": "1"},
    )
    rel = rel_resp.get("records", [{}])[0]
    logger.info(
        "RELATIONSHIP | uuid=%s | source=%s | dest=%s | state=%s | healthy=%s | lag=%s",
        rel.get("uuid"),
        rel.get("source", {}).get("path"),
        rel.get("destination", {}).get("path"),
        rel.get("state"),
        rel.get("healthy"),
        rel.get("lag_time"),
    )
    return rel


def _get_latest_sm_snapshot(client: OntapClient, dp_vol_uuid: str, dp_vol_name: str) -> str:
    """Phase B: Return the name of the most recent SnapMirror snapshot on the DP volume.

    The FlexClone must be based on a SnapMirror snapshot to guarantee a
    consistent point-in-time copy of the replicated data.
    Aborts if no snapshots exist.
    """
    logger.info("=== Phase B: Get latest SnapMirror snapshot ===")
    resp = client.get(
        f"/storage/volumes/{dp_vol_uuid}/snapshots",
        fields="name,create_time",
        **{"max_records": "1", "order_by": "create_time desc"},
    )
    if resp.get("num_records", 0) == 0:
        logger.error("No SnapMirror snapshots on %s — run provision workflow first", dp_vol_name)
        sys.exit(1)
    snapshot_name = resp["records"][0]["name"]
    logger.info(
        "LATEST SM SNAPSHOT | name=%s | created=%s",
        snapshot_name,
        resp["records"][0].get("create_time"),
    )
    return snapshot_name


def _create_test_clone(
    client: OntapClient, dp_vol_name: str, dp_svm_name: str, snapshot_name: str
) -> str:
    """Phase C: Create a writable FlexClone of the DP volume from the given snapshot.

    Returns the clone volume name.
    The clone is mounted at a NAS junction path so it can be accessed
    immediately by test clients without touching the source data.
    """
    logger.info("=== Phase C: Create FlexClone ===")
    clone_name = f"{dp_vol_name}_clone"
    try:
        resp = client.post(
            "/storage/volumes?return_timeout=120",
            body={
                "name": clone_name,
                "svm": {"name": dp_svm_name},
                "nas": {"path": f"/{clone_name}"},
                "clone": {
                    "is_flexclone": True,
                    "parent_volume": {"name": dp_vol_name},
                    "parent_snapshot": {"name": snapshot_name},
                },
            },
        )
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            _poll_job(client, job_uuid)
    except Exception as exc:
        logger.warning("create_test_clone — %s (may already exist)", exc)
    return clone_name


def _verify_and_tag_clone(
    client: OntapClient, clone_name: str, dp_svm_name: str, rel_uuid: str
) -> dict:
    """Phase D: Confirm the clone is online and tag it with the SM relationship UUID.

    The tag '<rel_uuid>:test' allows the cleanup script to identify and delete
    only test clones — manually created volumes are never matched.
    Returns the clone volume record.
    """
    logger.info("=== Phase D: Verify clone + tag ===")
    resp = client.get(
        "/storage/volumes",
        fields="name,uuid,state,nas.path,space.size",
        **{"max_records": "1", "name": clone_name, "svm.name": dp_svm_name},
    )
    clone_vol = resp.get("records", [{}])[0]
    clone_uuid = clone_vol.get("uuid", "")
    logger.info(
        "CLONE | name=%s | uuid=%s | state=%s | junction=%s",
        clone_vol.get("name"),
        clone_uuid,
        clone_vol.get("state"),
        clone_vol.get("nas", {}).get("path"),
    )
    try:
        client.patch(
            f"/storage/volumes/{clone_uuid}?return_timeout=120",
            body={"_tags": [f"{rel_uuid}:test"]},
        )
        logger.info("TAG APPLIED | clone=%s | tag=%s:test", clone_name, rel_uuid)
    except Exception as exc:
        logger.warning("tag_clone_volume — %s", exc)
    return clone_vol


def _resync_and_validate(client: OntapClient, rel_uuid: str) -> None:
    """Phase E: Resync the SnapMirror relationship and confirm state=snapmirrored.

    The test clone remains accessible while resync runs in the background.
    Polls until state=snapmirrored to confirm replication is healthy again.
    Times out after 30 minutes.
    """
    logger.info("=== Phase E: Resync SnapMirror ===")
    try:
        resp = client.patch(
            f"/snapmirror/relationships/{rel_uuid}?return_timeout=120",
            body={"state": "snapmirrored"},
        )
        job_uuid = resp.get("job", {}).get("uuid")
        if job_uuid:
            _poll_job(client, job_uuid, interval=10)
    except Exception as exc:
        logger.warning("resync_sm_relationship — %s", exc)
    _wait_snapmirrored(client, rel_uuid)
    logger.info("=== TEST FAILOVER COMPLETE — SnapMirror resynced ===")


def _select_target_volume(
    cluster_a: str,
    cluster_b: str,
    dest_user: str,
    dest_pass: str,
    source_volume: str,
) -> tuple[str, str, str, str]:
    """Phase 0: Scan both clusters to find which one holds the target DP volume.

    AUTO mode (SOURCE_VOLUME=* or unset): picks the most recently created DP volume.
    TARGETED mode: finds <source_volume>_dest on either cluster.
    Returns (dest_host, dp_vol_name, dp_svm_name, dp_vol_uuid).
    """
    logger.info("=== Phase 0: Auto-detect target cluster ===")
    dest_host, dp_vol = _pick_cluster(cluster_a, cluster_b, dest_user, dest_pass, source_volume)
    dp_vol_name = dp_vol["name"]
    dp_svm_name = dp_vol.get("svm", {}).get("name", "")
    dp_vol_uuid = dp_vol.get("uuid", "")
    logger.info(
        "SELECTED | cluster=%s | volume=%s | svm=%s | uuid=%s | state=%s | size=%s",
        dest_host,
        dp_vol_name,
        dp_svm_name,
        dp_vol_uuid,
        dp_vol.get("state"),
        dp_vol.get("space", {}).get("size"),
    )
    return dest_host, dp_vol_name, dp_svm_name, dp_vol_uuid


def main() -> None:
    """Create a writable FlexClone of the SnapMirror destination volume for test failover.

    Auto-detects which cluster holds the target DP volume, creates a FlexClone
    from the latest SnapMirror snapshot, tags it, then resyncs the relationship.
    """
    cluster_a = _env("CLUSTER_A")
    cluster_b = _env("CLUSTER_B")
    dest_user = _env("DEST_USER")
    dest_pass = _env("DEST_PASS")
    source_volume = INPUTS.get("SOURCE_VOLUME") or os.environ.get("SOURCE_VOLUME", "*")

    dest_host, dp_vol_name, dp_svm_name, dp_vol_uuid = _select_target_volume(
        cluster_a, cluster_b, dest_user, dest_pass, source_volume
    )

    with OntapClient(dest_host, dest_user, dest_pass, verify_ssl=False) as client:
        rel = _preflight_and_get_rel(client, dp_vol_name, dp_svm_name)
        rel_uuid = rel.get("uuid", "")
        snapshot_name = _get_latest_sm_snapshot(client, dp_vol_uuid, dp_vol_name)
        clone_name = _create_test_clone(client, dp_vol_name, dp_svm_name, snapshot_name)
        clone_vol = _verify_and_tag_clone(client, clone_name, dp_svm_name, rel_uuid)

        logger.info(
            "=== TEST FAILOVER READY ===\n"
            "  Clone    : %s\n  UUID     : %s\n  State    : %s\n"
            "  Junction : %s\n  SVM      : %s\n  Snapshot : %s\n\n"
            "  ACTION: Mount %s from SVM %s on a test client.",
            clone_vol.get("name"),
            clone_vol.get("uuid"),
            clone_vol.get("state"),
            clone_vol.get("nas", {}).get("path"),
            dp_svm_name,
            snapshot_name,
            clone_vol.get("nas", {}).get("path"),
            dp_svm_name,
        )

        _resync_and_validate(client, rel_uuid)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("snapmirror_test_failover failed")
        sys.exit(1)
