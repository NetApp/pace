#!/usr/bin/env python3
"""SnapMirror Provision — Destination-Managed view.

Equivalent to:  orchestrio run yaml-workflows/workflows/snapmirror_provision_dest_managed.yaml

All SnapMirror API calls driven from the DESTINATION cluster.
Source RW volume must already exist; dest DP volume is auto-created.

Steps:
    1. Verify source cluster connectivity
    2. Verify dest cluster connectivity
    3. Get cluster peer name (from dest peer list)
    4. Validate source volume exists and is RW
    5. Get dest aggregate
    6. Auto-create dest DP volume (skip if already exists)
    7. Validate dest DP volume exists
    8. Check if relationship already exists
    9. Create + initialize SnapMirror relationship
    10. Poll create/init job
    11. Fetch relationship UUID
    12. Initialize relationship (trigger baseline transfer)
    13. Wait for state = snapmirrored
    14. Validate health + print final report

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
    python snapmirror_provision_dest_managed.py
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
    "SOURCE_HOST": "",  # source cluster management IP — set via SOURCE_HOST env var
    "SOURCE_USER": "admin",
    "SOURCE_PASS": "",  # set via SOURCE_PASS env var — never hardcode
    "SOURCE_SVM": "svm1",  # source SVM name
    "SOURCE_VOLUME": "vol_py1",  # source RW volume name
    "DEST_HOST": "",  # destination cluster management IP — set via DEST_HOST env var
    "DEST_USER": "admin",
    "DEST_PASS": "",  # set via DEST_PASS env var — never hardcode
    "DEST_SVM": "vs0",  # destination SVM name
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


def _get_ic_lif_ips(client: OntapClient) -> list[str]:
    """Return intercluster LIF IPs from the given cluster."""
    resp = client.get(
        "/network/ip/interfaces",
        fields="name,ip.address,services",
        **{"max_records": "50"},
    )
    return [
        r["ip"]["address"]
        for r in resp.get("records", [])
        if any("intercluster" in str(s) for s in r.get("services", []))
        and r.get("ip", {}).get("address")
    ]


def _check_ic_lif_preconditions(
    src: OntapClient, dst: OntapClient, src_ips: list[str], dst_ips: list[str]
) -> None:
    """Validate IC LIFs exist and warn if subnets are incompatible.

    Aborts if either cluster has no IC LIFs.
    Warns (but continues) if IC LIFs are on different subnets — SnapMirror
    transfers will fail with error 13303812 unless TCP 11104/11105 is open
    between the two subnets.
    """
    if not src_ips:
        logger.error(
            "PRE-CONDITION FAILED | Source cluster has no intercluster LIFs.\n"
            "  SnapMirror requires at least one IC LIF on each cluster.\n"
            "  Create one via System Manager: Network → IP Interfaces → Add → Role: Intercluster\n"
            "  Or via CLI: network interface create -role intercluster -home-port e0d "
            "-address <IP> -netmask <mask>"
        )
        sys.exit(1)
    if not dst_ips:
        logger.error(
            "PRE-CONDITION FAILED | Dest cluster has no intercluster LIFs.\n"
            "  SnapMirror requires at least one IC LIF on each cluster.\n"
            "  Create one via System Manager: Network → IP Interfaces → Add → Role: Intercluster\n"
            "  Or via CLI: network interface create -role intercluster -home-port e0d "
            "-address <IP> -netmask <mask>"
        )
        sys.exit(1)

    def _subnet24(ip: str) -> str:
        return ".".join(ip.split(".")[:3])

    src_subnets = {_subnet24(ip) for ip in src_ips}
    dst_subnets = {_subnet24(ip) for ip in dst_ips}

    if src_subnets.isdisjoint(dst_subnets):
        logger.warning(
            "PRE-CONDITION WARNING | IC LIFs are on different subnets.\n"
            "  src subnets : %s\n"
            "  dst subnets : %s\n"
            "  SnapMirror data transfers require TCP 11104 and 11105 to be open\n"
            "  between these subnets. If not routed, transfers will fail with:\n"
            "    'Initialize operation failed. Volume not found. (13303812)'\n"
            "  Resolution options:\n"
            "    1. Ask your lab admin to open TCP 11104/11105 between %s <-> %s\n"
            "    2. Move IC LIFs to a shared subnet on both clusters\n"
            "    3. Use a different cluster pair whose IC LIFs share a subnet",
            sorted(src_subnets),
            sorted(dst_subnets),
            next(iter(src_subnets)),
            next(iter(dst_subnets)),
        )
    else:
        logger.info(
            "PRE-CONDITION OK   | IC LIFs share a common subnet %s — transfers should work",
            sorted(src_subnets & dst_subnets),
        )


def _setup_cluster_peer(
    src: OntapClient, dst: OntapClient, source_svm: str, dest_svm: str
) -> tuple[str, str, str]:
    """Ensure cluster peer exists between src and dst.

    Returns (src_peer_name, dst_peer_name, dst_peer_uuid).
    Aborts with a clear error if intercluster LIFs are missing.
    """
    _OK = {"available", "partial", "pending"}
    dst_cp = dst.get("/cluster/peers", fields="name,uuid,status.state", **{"max_records": "10"})
    dst_peers = [p for p in dst_cp.get("records", []) if p.get("status", {}).get("state") in _OK]
    if dst_peers:
        p = dst_peers[0]
        src_cp = src.get(
            "/cluster/peers", fields="name,uuid,status.state", **{"max_records": "10"}
        )
        src_peers = [
            q for q in src_cp.get("records", []) if q.get("status", {}).get("state") in _OK
        ]
        src_peer_name = src_peers[0]["name"] if src_peers else ""
        src_ips = _get_ic_lif_ips(src)
        dst_ips = _get_ic_lif_ips(dst)
        logger.info(
            "CLUSTER PEER   | already peered — dst sees src as '%s' (state=%s) — skipping",
            p["name"],
            p.get("status", {}).get("state"),
        )
        logger.info("IC LIFs        | src=%s  dst=%s", src_ips, dst_ips)
        _check_ic_lif_preconditions(src, dst, src_ips, dst_ips)
        return src_peer_name, p["name"], p["uuid"]

    logger.info("CLUSTER PEER   | no existing peer found — auto-creating")
    src_ips = _get_ic_lif_ips(src)
    dst_ips = _get_ic_lif_ips(dst)
    if not src_ips:
        logger.error(
            "ABORTED — no intercluster LIFs found on source cluster.\n"
            "  Create one first via System Manager or CLI:\n"
            "    network interface create -vserver <cluster> -lif ic_lif1 -role intercluster\n"
            "      -home-node <node> -home-port e0d -address <IP> -netmask <mask>"
        )
        sys.exit(1)
    if not dst_ips:
        logger.error(
            "ABORTED — no intercluster LIFs found on dest cluster.\n"
            "  Create one first via System Manager or CLI:\n"
            "    network interface create -vserver <cluster> -lif ic_lif1 -role intercluster\n"
            "      -home-node <node> -home-port e0d -address <IP> -netmask <mask>"
        )
        sys.exit(1)
    logger.info("CLUSTER PEER   | src IC LIFs=%s  dst IC LIFs=%s", src_ips, dst_ips)
    _check_ic_lif_preconditions(src, dst, src_ips, dst_ips)

    try:
        resp = src.post(
            "/cluster/peers",
            body={
                "peer_addresses": dst_ips,
                "generate_passphrase": True,
                "encryption": {"proposed": "tls-psk"},
                "initial_allowed_svms": [{"name": source_svm}],
            },
        )
        passphrase = resp.get("passphrase", "")
        logger.info("CLUSTER PEER   | created on source")
    except Exception as exc:
        logger.error("CLUSTER PEER   | create on source failed: %s", exc)
        raise

    try:
        dst.post(
            "/cluster/peers",
            body={
                "peer_addresses": src_ips,
                "passphrase": passphrase,
                "initial_allowed_svms": [{"name": dest_svm}],
            },
        )
        logger.info("CLUSTER PEER   | accepted on dest")
    except Exception as exc:
        logger.error("CLUSTER PEER   | accept on dest failed: %s", exc)
        raise

    time.sleep(5)
    dst_cp2 = dst.get("/cluster/peers", fields="name,uuid,status.state", **{"max_records": "10"})
    dst_peers2 = [p for p in dst_cp2.get("records", []) if p.get("status", {}).get("state") in _OK]
    dst_peer_name = dst_peers2[0]["name"] if dst_peers2 else ""
    dst_peer_uuid = dst_peers2[0]["uuid"] if dst_peers2 else ""
    src_cp2 = src.get("/cluster/peers", fields="name,uuid,status.state", **{"max_records": "10"})
    src_peers2 = [p for p in src_cp2.get("records", []) if p.get("status", {}).get("state") in _OK]
    src_peer_name = src_peers2[0]["name"] if src_peers2 else ""
    logger.info("CLUSTER PEER   | dst sees src as '%s'", dst_peer_name)
    return src_peer_name, dst_peer_name, dst_peer_uuid


def _setup_svm_peer(
    src: OntapClient,
    dst: OntapClient,
    source_svm: str,
    dest_svm: str,
    src_peer_name: str,
    dst_peer_name: str,
    src_cluster_peer_uuid: str,
) -> str:
    """Ensure SVM peer exists between dest_svm and source_svm.

    Returns the source SVM alias used in SnapMirror source paths.
    """
    svm_resp = dst.get("/svm/peers", fields="uuid,name,state,peer", **{"svm.name": dest_svm})
    existing = [
        p
        for p in svm_resp.get("records", [])
        if p.get("state") in ("peered", "initiated")
        and p.get("peer", {}).get("cluster", {}).get("uuid") == src_cluster_peer_uuid
    ]
    if existing:
        alias = existing[0].get("peer", {}).get("svm", {}).get("name", source_svm)
        logger.info(
            "SVM PEER       | already peered '%s' <-> '%s' (alias='%s', state=%s) — skipping",
            dest_svm,
            source_svm,
            alias,
            existing[0].get("state"),
        )
        return alias

    try:
        src.post(
            "/svm/peer-permissions",
            body={
                "svm": {"name": source_svm},
                "cluster_peer": {"name": src_peer_name},
                "applications": ["snapmirror"],
            },
        )
        logger.info("SVM PEER       | peer-permission granted on source")
    except Exception as exc:
        exc_s = str(exc)
        if "already exists" in exc_s or "duplicate" in exc_s.lower() or "13001" in exc_s:
            logger.info("SVM PEER       | peer-permission already exists — skipping")
        else:
            logger.error("SVM PEER       | peer-permission failed: %s", exc)
            raise

    try:
        resp = dst.post(
            "/svm/peers",
            body={
                "svm": {"name": dest_svm},
                "peer": {"svm": {"name": source_svm}, "cluster": {"name": dst_peer_name}},
                "applications": ["snapmirror"],
            },
        )
        peer_job = resp.get("job", {}).get("uuid", "")
        if peer_job:
            _poll_job(dst, peer_job)
        logger.info("SVM PEER       | created '%s' <-> '%s'", dest_svm, source_svm)
    except Exception as exc:
        exc_s = str(exc)
        if "already exists" in exc_s or "duplicate" in exc_s.lower() or "13001" in exc_s:
            logger.info("SVM PEER       | already exists — skipping")
        else:
            logger.error("SVM PEER       | create failed: %s", exc)
            raise

    svm_resp2 = dst.get("/svm/peers", fields="uuid,name,state,peer", **{"svm.name": dest_svm})
    peers2 = [
        p
        for p in svm_resp2.get("records", [])
        if p.get("peer", {}).get("cluster", {}).get("uuid") == src_cluster_peer_uuid
    ]
    alias = (
        peers2[0].get("peer", {}).get("svm", {}).get("name", source_svm) if peers2 else source_svm
    )
    return alias


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
        # ── Phase A: Source pre-flight ────────────────────────────────────
        # Verify source cluster is reachable and the source volume is a
        # writable (RW) type — DP volumes cannot be used as a SnapMirror source.
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
            "SOURCE VOLUME  | svm=%s | name=%s | uuid=%s | state=%s | type=%s | size=%s",
            source_svm,
            src_vol["name"],
            src_vol["uuid"],
            src_vol["state"],
            src_vol["type"],
            src_vol.get("space", {}).get("size"),
        )

        # ── Phase B: Dest pre-flight ──────────────────────────────────────
        # Verify destination cluster connectivity, get the cluster peer name
        # (required to reference the source from the destination side), and
        # pick an aggregate to host the new destination DP volume.
        logger.info("=== Phase B: Dest pre-flight ===")
        dst_cluster = dst.get("/cluster", fields="name,version")
        logger.info(
            "DEST CLUSTER   | name=%s | ontap=%s",
            dst_cluster.get("name"),
            dst_cluster.get("version", {}).get("full"),
        )

        # ── Phase B0: Cluster peer setup ──────────────────────────────────
        logger.info("=== Phase B0: Cluster peer setup ===")
        src_peer_name, peer_name, dst_peer_uuid = _setup_cluster_peer(
            src, dst, source_svm, dest_svm
        )

        aggr_resp = dst.get(
            "/storage/aggregates",
            fields="name,state",
            **{"max_records": "1"},
        )
        aggr_name = aggr_resp.get("records", [{}])[0].get("name", "")
        logger.info("DEST AGGREGATE | name=%s", aggr_name)

        # ── Phase B1: SVM peer setup ──────────────────────────────────────
        logger.info("=== Phase B1: SVM peer setup ===")
        source_svm_alias = _setup_svm_peer(
            src, dst, source_svm, dest_svm, src_peer_name, peer_name, dst_peer_uuid
        )

        # ── Phase C: Dest volume setup ────────────────────────────────────
        # Auto-create a DP volume on the destination to receive SnapMirror
        # transfers. The create is skipped silently if the volume already exists.
        logger.info("=== Phase C: Dest volume setup ===")
        try:
            dst.post(
                "/storage/volumes?return_timeout=120",
                body={
                    "name": dest_volume,
                    "type": "dp",
                    "svm": {"name": dest_svm},
                    "aggregates": [{"name": aggr_name}],
                    "space": {"size": str(src_vol.get("space", {}).get("size", ""))},
                },
            )
            logger.info(
                "DEST VOLUME    | created '%s' on aggregate '%s'",
                dest_volume,
                aggr_name,
            )
        except Exception as exc:
            logger.info("create_dest_volume — %s (skipped — may already exist)", exc)

        dst_vol_resp = dst.get(
            "/storage/volumes",
            fields="name,uuid,state,type",
            **{"max_records": "1", "name": dest_volume, "svm.name": dest_svm},
        )
        dst_vol = dst_vol_resp.get("records", [{}])[0]
        logger.info(
            "DEST VOLUME    | svm=%s | name=%s | uuid=%s | state=%s | type=%s",
            dest_svm,
            dst_vol.get("name"),
            dst_vol.get("uuid"),
            dst_vol.get("state"),
            dst_vol.get("type"),
        )

        # ── Phase D: Relationship setup ───────────────────────────────────
        # Create and initialize the SnapMirror relationship from destination.
        # If the relationship already exists the POST fails gracefully.
        # After create, the relationship UUID is fetched and a baseline
        # transfer is triggered explicitly to start data replication.
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
                        "path": f"{source_svm_alias}:{source_volume}",
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
            logger.info("create_and_initialize_relationship — %s (may already exist)", exc)

        rel_resp = dst.get(
            "/snapmirror/relationships",
            fields="uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
            **{"destination.path": f"{dest_svm}:{dest_volume}", "max_records": "1"},
        )
        rel_records = rel_resp.get("records", [])
        if not rel_records:
            logger.error(
                "ABORTED — SnapMirror relationship not found for '%s:%s'", dest_svm, dest_volume
            )
            sys.exit(1)
        rel = rel_records[0]
        rel_uuid = rel.get("uuid", "")
        logger.info(
            "RELATIONSHIP   | uuid=%s | state=%s | healthy=%s | policy=%s",
            rel_uuid,
            rel.get("state"),
            rel.get("healthy"),
            rel.get("policy", {}).get("name"),
        )

        try:
            dst.post(
                f"/snapmirror/relationships/{rel_uuid}/transfers?return_timeout=120",
                body={},
            )
        except Exception as exc:
            exc_s = str(exc)
            if "13303812" in exc_s:
                src_ips = _get_ic_lif_ips(src)
                dst_ips = _get_ic_lif_ips(dst)
                logger.error(
                    "ABORTED — SnapMirror initialize failed: intercluster LIF connectivity issue.\n"
                    "  Error   : %s\n"
                    "  src IC  : %s\n"
                    "  dst IC  : %s\n"
                    "  Cause   : TCP ports 11104/11105 are likely blocked between these IPs.\n"
                    "  Fix     : Ask your lab admin to open TCP 11104 and 11105 between\n"
                    "            %s <-> %s",
                    exc_s,
                    src_ips,
                    dst_ips,
                    src_ips[0] if src_ips else "<src-ic-lif>",
                    dst_ips[0] if dst_ips else "<dst-ic-lif>",
                )
                sys.exit(1)
            logger.info("initialize_relationship — %s (may already be initialized)", exc)

        # ── Phase E: Convergence polling ──────────────────────────────────
        # Poll the relationship until state=snapmirrored (baseline transfer done).
        logger.info("=== Phase E: Convergence polling ===")
        _wait_snapmirrored(dst, rel_uuid)

        # ── Phase F: Final validation ─────────────────────────────────────
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
    except Exception:
        logger.exception("snapmirror_provision_dest_managed failed")
        sys.exit(1)
