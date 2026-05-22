# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

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

from ontap_client import OntapApiError, OntapClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USER INPUTS — fill in your values here before running
# ---------------------------------------------------------------------------
INPUTS = {
    "SOURCE_HOST": "",  # source cluster management IP — set via SOURCE_HOST env var
    "SOURCE_USER": "admin",
    "SOURCE_PASS": "",  # set via SOURCE_PASS env var — never hardcode
    "SOURCE_SVM": "",  # source SVM name
    "SOURCE_VOLUME": "",  # source RW volume name
    "DEST_HOST": "",  # destination cluster management IP — set via DEST_HOST env var
    "DEST_USER": "admin",
    "DEST_PASS": "",  # set via DEST_PASS env var — never hardcode
    "DEST_SVM": "",  # destination SVM name
    "SM_POLICY": "Asynchronous",  # SnapMirror policy (optional)
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


def _phase_a_source_preflight(
    src: OntapClient, source_svm: str, source_volume: str, source_host: str
) -> dict:
    """Verify source cluster connectivity and validate the source volume.

    Returns the source volume record. Aborts if missing or DP type.
    """
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
    return src_vol


def _phase_b_dest_preflight(dst: OntapClient) -> tuple[str, str]:
    """Query the dest cluster for its peer name and best available aggregate.

    Returns ``(peer_name, aggr_name)``.
    """
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
    return peer_name, aggr_name


def _phase_c_dest_volume_setup(
    dst: OntapClient,
    dest_svm: str,
    dest_volume: str,
    aggr_name: str,
    src_vol: dict,
) -> None:
    """Create the destination DP volume if it does not already exist."""
    check_dest = dst.get(
        "/storage/volumes",
        fields="name,uuid,state,type",
        **{"max_records": "1", "name": dest_volume, "svm.name": dest_svm},
    )
    if check_dest.get("num_records", 0) == 0:
        logger.info("Creating dest DP volume '%s' on '%s'...", dest_volume, aggr_name)
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


def _phase_d_setup_relationship(
    dst: OntapClient,
    source_svm: str,
    source_volume: str,
    dest_svm: str,
    dest_volume: str,
    peer_name: str,
    sm_policy: str,
) -> None:
    """Create and initialize the SnapMirror relationship (idempotent)."""
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
            dst.poll_job(job_uuid)
    except Exception as exc:
        logger.warning("create_and_initialize_relationship — %s (may already exist)", exc)


def _abort_ic_lif_unreachable(
    src: OntapClient,
    dst: OntapClient,
    source_host: str,
    dest_host: str,
    exc: OntapApiError,
) -> None:
    """Log a detailed error about unreachable IC LIFs and abort."""
    src_ips = [
        r["ip"]["address"]
        for r in src.get(
            "/network/ip/interfaces",
            fields="ip.address,services",
            **{"max_records": "50"},
        ).get("records", [])
        if any("intercluster" in str(s) for s in r.get("services", []))
    ]
    dst_ips = [
        r["ip"]["address"]
        for r in dst.get(
            "/network/ip/interfaces",
            fields="ip.address,services",
            **{"max_records": "50"},
        ).get("records", [])
        if any("intercluster" in str(s) for s in r.get("services", []))
    ]
    logger.error(
        "ABORTED — SnapMirror initialize failed: source volume not reachable.\n"
        "  ONTAP error : %s\n"
        "  Likely cause: TCP 11104/11105 is blocked between IC LIFs.\n"
        "  src IC LIFs : %s\n"
        "  dst IC LIFs : %s\n"
        "  Note        : SnapMirror transfers are always initiated by the DEST\n"
        "                cluster. With SOURCE=%s and DEST=%s, the dest cluster\n"
        "                (%s) must reach the source (%s) on TCP 11104/11105.\n"
        "  Fix         : Open TCP 11104/11105 in that direction, or swap\n"
        "                SOURCE/DEST so the working direction is used.",
        exc,
        src_ips,
        dst_ips,
        source_host,
        dest_host,
        dest_host,
        source_host,
    )
    sys.exit(1)


def _phase_e_convergence_polling(
    src: OntapClient,
    dst: OntapClient,
    source_host: str,
    dest_host: str,
    dest_svm: str,
    dest_volume: str,
) -> str:
    """Kick off the initial transfer and wait until the relationship is snapmirrored.

    Returns the relationship UUID.
    """
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
    except OntapApiError as exc:
        err = exc.detail.get("error", {}) if isinstance(exc.detail, dict) else {}
        if err.get("code") == "13303812" and "not found" in err.get("message", ""):
            _abort_ic_lif_unreachable(src, dst, source_host, dest_host, exc)
        logger.warning("initialize_relationship — %s (may already be initialized)", exc)
    except Exception as exc:
        logger.warning("initialize_relationship — %s (may already be initialized)", exc)

    dst.wait_snapmirrored(rel_uuid)
    return rel_uuid


def main() -> None:
    """Orchestrate all six phases (A–F) to provision a SnapMirror relationship from the source cluster."""
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
        logger.info("=== Phase A: Source pre-flight ===")
        src_vol = _phase_a_source_preflight(src, source_svm, source_volume, source_host)

        logger.info("=== Phase B: Dest pre-flight ===")
        peer_name, aggr_name = _phase_b_dest_preflight(dst)

        logger.info("=== Phase C: Dest volume setup ===")
        _phase_c_dest_volume_setup(dst, dest_svm, dest_volume, aggr_name, src_vol)

        logger.info("=== Phase D: Relationship setup ===")
        _phase_d_setup_relationship(
            dst, source_svm, source_volume, dest_svm, dest_volume, peer_name, sm_policy
        )

        logger.info("=== Phase E: Convergence polling ===")
        rel_uuid = _phase_e_convergence_polling(
            src, dst, source_host, dest_host, dest_svm, dest_volume
        )

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
