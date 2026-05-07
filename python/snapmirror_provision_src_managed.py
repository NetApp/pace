#!/usr/bin/env python3
"""SnapMirror Provision — Source-Managed view.

Connects to BOTH clusters for pre-flight verification, then drives all
relationship/volume API calls from the DESTINATION cluster (ONTAP requirement).

Phases:
    A  Source pre-flight  — verify source cluster + volume
    B  Dest pre-flight    — verify dest cluster + aggregate
    C  Dest volume        — auto-create DP volume if missing
    D  Relationship       — create + initialize SnapMirror
    E  Convergence        — poll until state=snapmirrored
    F  Validation         — health check + final report

Prerequisites:
    1. pip install -r requirements.txt
    2. ONTAP 9.8+ on both clusters
    3. SnapMirror licence installed on both clusters
    4. At least one intercluster LIF on each cluster
    5. Cluster peer relationship already exists between source and dest clusters
    6. SVM peer relationship already exists (source SVM <-> dest SVM)
    7. Source RW volume (SOURCE_VOLUME) already exists on SOURCE_SVM
    8. At least one online aggregate on the destination cluster
    9. Admin credentials for both clusters

Usage::

    export SOURCE_HOST=10.x.x.x  SOURCE_USER=admin  SOURCE_PASS=secret
    export SOURCE_SVM=vs0         SOURCE_VOLUME=vol_rw_01
    export DEST_HOST=10.y.y.y     DEST_USER=admin    DEST_PASS=secret
    export DEST_SVM=vs1
    export SM_POLICY=Asynchronous
    python snapmirror_provision_src_managed.py
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
    "SOURCE_HOST": "",  # source cluster management IP — never hardcode
    "SOURCE_USER": "admin",
    "SOURCE_PASS": "",  # set via SOURCE_PASS env var
    "SOURCE_SVM": "vs0",  # source SVM name
    "SOURCE_VOLUME": "",  # source RW volume name
    "DEST_HOST": "",  # destination cluster management IP — never hardcode
    "DEST_USER": "admin",
    "DEST_PASS": "",  # set via DEST_PASS env var
    "DEST_SVM": "vs1",  # destination SVM name
    "SM_POLICY": "Asynchronous",  # SnapMirror policy (optional)
}
# ---------------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
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


def main() -> None:
    source_host = _env("SOURCE_HOST")
    source_user = _env("SOURCE_USER")
    source_pass = _env("SOURCE_PASS")
    source_svm = _env("SOURCE_SVM")
    source_volume = _env("SOURCE_VOLUME")

    dest_host = _env("DEST_HOST")
    dest_user = _env("DEST_USER")
    dest_pass = _env("DEST_PASS")
    dest_svm = _env("DEST_SVM")
    sm_policy = os.environ.get("SM_POLICY", "Asynchronous")

    dest_volume = f"{source_volume}_dest"

    src = OntapClient(source_host, source_user, source_pass, verify_ssl=False)
    dst = OntapClient(dest_host, dest_user, dest_pass, verify_ssl=False)

    with src, dst:
        # ── Phase A: Source pre-flight ───────────────────────────────────────────
        # Verify source cluster is reachable and the specified volume is a
        # writable (RW) type. DP volumes cannot be used as a SnapMirror source.
        logger.info("=== Phase A: Source pre-flight ===")
        src_cluster = src.get("/cluster", fields="name,version")
        logger.info(
            "SOURCE CLUSTER | name=%s | ontap=%s",
            src_cluster.get("name"),
            src_cluster.get("version", {}).get("full"),
        )

        src_vol_resp = src.get(
            "/storage/volumes",
            fields="name,uuid,state,type,space.size",
            **{"max_records": "1", "name": source_volume, "svm.name": source_svm},
        )
        if src_vol_resp.get("num_records", 0) == 0:
            logger.error(
                "ABORTED — source volume '%s' not found on %s",
                source_volume,
                source_host,
            )
            sys.exit(1)
        src_vol = src_vol_resp["records"][0]
        if src_vol.get("type") == "dp":
            logger.error("ABORTED — source volume is type=dp; specify the RW volume")
            sys.exit(1)
        logger.info(
            "SOURCE VOLUME  | name=%s | uuid=%s | state=%s | type=%s | size=%s",
            src_vol["name"],
            src_vol["uuid"],
            src_vol["state"],
            src_vol["type"],
            src_vol.get("space", {}).get("size"),
        )

        # ── Phase B: Dest pre-flight ─────────────────────────────────────
        # Verify destination cluster connectivity. Retrieve the cluster peer name
        # (used to reference the source from the destination side) and pick an
        # available aggregate to host the new destination DP volume.
        logger.info("=== Phase B: Dest pre-flight ===")
        dst_cluster = dst.get("/cluster", fields="name,version")
        logger.info(
            "DEST CLUSTER   | name=%s | ontap=%s",
            dst_cluster.get("name"),
            dst_cluster.get("version", {}).get("full"),
        )

        peer_resp = dst.get(
            "/cluster/peers",
            fields="name,status.state",
            **{"max_records": "1"},
        )
        peer_name = peer_resp.get("records", [{}])[0].get("name", "")
        logger.info("CLUSTER PEER   | name=%s", peer_name)

        aggr_resp = dst.get(
            "/storage/aggregates",
            fields="name,space.block_storage.available",
            state="online",
            **{"max_records": "1", "order_by": "space.block_storage.available desc"},
        )
        aggr_name = aggr_resp.get("records", [{}])[0].get("name", "")
        logger.info("DEST AGGREGATE | name=%s", aggr_name)

        # ── Phase C: Auto-create dest DP volume ──────────────────────────
        # Check if the destination DP volume already exists; create it if not.
        # DP (data-protection) type volumes are required as SnapMirror destinations.
        # Volume creation is skipped with a warning if it already exists.
        logger.info("=== Phase C: Dest volume setup ===")
        check_dest = dst.get(
            "/storage/volumes",
            fields="name,uuid,state,type",
            **{"max_records": "1", "name": dest_volume, "svm.name": dest_svm},
        )
        if check_dest.get("num_records", 0) == 0:
            logger.info("Creating dest DP volume '%s' on '%s'…", dest_volume, aggr_name)
            try:
                dst.post(
                    "/storage/volumes?return_timeout=120",
                    body={
                        "name": dest_volume,
                        "type": "dp",
                        "svm": {"name": dest_svm},
                        "aggregates": [{"name": aggr_name}],
                        "size": str(src_vol.get("space", {}).get("size", "")),
                    },
                )
            except Exception as exc:
                logger.warning("create_dest_volume — %s (may already exist)", exc)
        else:
            logger.info("Dest volume '%s' already exists — skipping create", dest_volume)

        dst_vol_resp = dst.get(
            "/storage/volumes",
            fields="name,uuid,state,type",
            **{"max_records": "1", "name": dest_volume, "svm.name": dest_svm},
        )
        dst_vol = dst_vol_resp.get("records", [{}])[0]
        logger.info(
            "DEST VOLUME    | name=%s | uuid=%s | state=%s | type=%s",
            dst_vol.get("name"),
            dst_vol.get("uuid"),
            dst_vol.get("state"),
            dst_vol.get("type"),
        )

        # ── Phase D: Create + initialize relationship ─────────────────────
        # Create the SnapMirror relationship and trigger a baseline transfer.
        # All relationship API calls are made from the destination cluster
        # (ONTAP requirement). POST is skipped gracefully if it already exists.
        logger.info("=== Phase D: Relationship setup ===")
        existing = dst.get(
            "/snapmirror/relationships",
            fields="uuid,state,healthy",
            **{"destination.path": f"{dest_svm}:{dest_volume}", "max_records": "1"},
        )
        logger.info("RELATIONSHIP CHECK | existing=%d", existing.get("num_records", 0))

        try:
            create_resp = dst.post(
                "/snapmirror/relationships?return_timeout=120",
                body={
                    "source": {
                        "path": f"{source_svm}:{source_volume}",
                        "cluster": {"name": peer_name},
                    },
                    "destination": {"path": f"{dest_svm}:{dest_volume}"},
                    "policy": {"name": sm_policy},
                },
            )
            job_uuid = create_resp.get("job", {}).get("uuid")
            if job_uuid:
                _poll_job(dst, job_uuid)
        except Exception as exc:
            logger.warning("create_and_initialize_relationship — %s (may already exist)", exc)

        # ── Phase E: Convergence polling ─────────────────────────────────
        # Fetch the relationship UUID, trigger a baseline transfer explicitly,
        # then poll until state=snapmirrored confirming initial replication is done.
        # Times out after 30 minutes.
        logger.info("=== Phase E: Convergence polling ===")
        rel_resp = dst.get(
            "/snapmirror/relationships",
            fields="uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
            **{"destination.path": f"{dest_svm}:{dest_volume}", "max_records": "1"},
        )
        rel = rel_resp.get("records", [{}])[0]
        rel_uuid = rel.get("uuid", "")
        logger.info(
            "RELATIONSHIP FOUND | uuid=%s | state=%s | healthy=%s",
            rel_uuid,
            rel.get("state"),
            rel.get("healthy"),
        )

        try:
            dst.post(
                f"/snapmirror/relationships/{rel_uuid}/transfers?return_timeout=120",
                body={},
            )
        except Exception as exc:
            logger.warning("initialize_relationship — %s (may already be initialized)", exc)

        _wait_snapmirrored(dst, rel_uuid)

        # ── Phase F: Final validation ─────────────────────────────────────
        # Fetch the final relationship state and print a human-readable summary
        # with source, destination, health status, policy, and lag time.
        logger.info("=== Phase F: Final validation ===")
        final = dst.get(
            f"/snapmirror/relationships/{rel_uuid}",
            fields="uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
        )
        logger.info(
            "=== SNAPMIRROR PROVISION COMPLETE ===\n"
            "  source      : %s:%s\n"
            "  destination : %s:%s\n"
            "  state       : %s\n"
            "  healthy     : %s\n"
            "  policy      : %s\n"
            "  lag_time    : %s",
            source_svm,
            source_volume,
            dest_svm,
            dest_volume,
            final.get("state"),
            final.get("healthy"),
            final.get("policy", {}).get("name"),
            final.get("lag_time"),
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("snapmirror_provision_src_managed failed")
        sys.exit(1)
