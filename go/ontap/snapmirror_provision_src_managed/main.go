// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// SnapMirror Provision — Source-Managed view.
//
// Connects to BOTH clusters for pre-flight verification, then drives all
// relationship/volume API calls from the DESTINATION cluster (ONTAP requirement).
//
// Phases:
//
//	A  Source pre-flight  — verify source cluster + volume
//	B  Dest pre-flight    — verify dest cluster + aggregate
//	C  Dest volume        — auto-create DP volume if missing
//	D  Relationship       — create + initialize SnapMirror
//	E  Convergence        — poll until state=snapmirrored
//	F  Validation         — health check + final report
//
// Prerequisites:
//  1. Go 1.22+ installed; run `cd go && go mod download` once to cache deps
//  2. ONTAP 9.8+ on both clusters
//  3. SnapMirror licence installed on both clusters
//  4. At least one intercluster LIF on each cluster
//  5. Cluster peer relationship must already exist between source and dest clusters
//     (this script does NOT auto-create peers — run snapmirror_provision_dest_managed
//     first, or set up peers manually via System Manager)
//  6. SVM peer relationship must already exist (source SVM <-> dest SVM)
//  7. Source RW volume (SOURCE_VOLUME) already exists on SOURCE_SVM
//  8. At least one online aggregate on the destination cluster
//  9. Admin credentials for both clusters
//
// Usage:
//
//	export SOURCE_HOST=10.x.x.x  SOURCE_USER=admin  SOURCE_PASS=secret
//	export SOURCE_SVM=vs0         SOURCE_VOLUME=vol_rw_01
//	export DEST_HOST=10.y.y.y     DEST_USER=admin    DEST_PASS=secret
//	export DEST_SVM=vs1
//	export SM_POLICY=Asynchronous
//	go run .
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	ontapclient "github.com/netapp/pace/go/ontap/ontapclient"
)

// ---------------------------------------------------------------------------

const pathSMRelationships = "/snapmirror/relationships"

// smRelConfig groups SnapMirror relationship parameters to keep function
// signatures within the 7-parameter limit.
type smRelConfig struct {
	sourceSVM, sourceVolume, destSVM, destVolume, peerName, smPolicy string
}

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	sourceHost := mustEnv("SOURCE_HOST")
	sourceUser := envOrDefault("SOURCE_USER", "admin")
	sourcePass := mustEnv("SOURCE_PASS")
	sourceSVM := mustEnv("SOURCE_SVM")
	sourceVolume := mustEnv("SOURCE_VOLUME")

	destHost := mustEnv("DEST_HOST")
	destUser := envOrDefault("DEST_USER", "admin")
	destPass := mustEnv("DEST_PASS")
	destSVM := mustEnv("DEST_SVM")
	smPolicy := envOrDefault("SM_POLICY", "Asynchronous")

	destVolume := envOrDefault("DEST_VOLUME", sourceVolume+"_dest")

	src := ontapclient.New(sourceHost, sourceUser, sourcePass, false)
	defer src.Close()
	dst := ontapclient.New(destHost, destUser, destPass, false)
	defer dst.Close()

	log.Println("=== Phase A: Source pre-flight ===")
	srcVolSize := smSrcPhaseA(ctx, src, sourceSVM, sourceVolume, sourceHost)

	log.Println("=== Phase B: Dest pre-flight ===")
	peerName, aggrName := smSrcPhaseB(ctx, dst)

	log.Println("=== Phase C: Dest volume setup ===")
	smSrcPhaseC(ctx, dst, destSVM, destVolume, aggrName, srcVolSize)

	log.Println("=== Phase D: Relationship setup ===")
	smCfg := smRelConfig{
		sourceSVM: sourceSVM, sourceVolume: sourceVolume,
		destSVM: destSVM, destVolume: destVolume,
		peerName: peerName, smPolicy: smPolicy,
	}
	relUUID := smSrcPhaseD(ctx, dst, smCfg)

	log.Println("=== Phase E: Convergence polling ===")
	if _, err := dst.WaitSnapmirrored(ctx, relUUID, 15*time.Second, 30*time.Minute); err != nil {
		log.Fatalf("wait snapmirrored: %v", err)
	}

	log.Println("=== Phase F: Final validation ===")
	smSrcPhaseF(ctx, dst, relUUID, sourceSVM, sourceVolume, destSVM, destVolume)
}

// smSrcPhaseA verifies the source cluster and validates the source volume.
// Returns srcVolSize as int64 bytes, ready to pass directly to the ONTAP size field.
func smSrcPhaseA(ctx context.Context, src *ontapclient.Client, sourceSVM, sourceVolume, sourceHost string) int64 {
	srcCluster, err := src.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get source cluster", err)
	log.Printf("SOURCE CLUSTER | name=%s | ontap=%s",
		ontapclient.NestedStr(srcCluster, "name"),
		ontapclient.NestedStr(srcCluster, "version", "full"))

	srcVolResp, err := src.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid,state,type,space.size",
		"max_records":          "1",
		"name":                 sourceVolume,
		ontapclient.KeySVMName: sourceSVM,
	})
	dieOnErr("get source volume", err)
	if ontapclient.NumRecords(srcVolResp) == 0 {
		log.Fatalf("ABORTED — source volume '%s' not found on %s", sourceVolume, sourceHost)
	}
	srcVol := ontapclient.Records(srcVolResp)[0]
	if ontapclient.NestedStr(srcVol, "type") == "dp" {
		log.Fatal("ABORTED — source volume is type=dp; specify the RW volume")
	}
	srcVolSize := int64(ontapclient.NestedFloat(srcVol, "space", "size"))
	log.Printf("SOURCE VOLUME  | name=%s | uuid=%s | state=%s | type=%s | size=%d",
		ontapclient.NestedStr(srcVol, "name"),
		ontapclient.NestedStr(srcVol, "uuid"),
		ontapclient.NestedStr(srcVol, "state"),
		ontapclient.NestedStr(srcVol, "type"),
		srcVolSize)
	return srcVolSize
}

// smSrcPhaseB verifies the dest cluster, fetches peer name and best aggregate.
// Returns (peerName, aggrName).
func smSrcPhaseB(ctx context.Context, dst *ontapclient.Client) (string, string) {
	dstCluster, err := dst.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get dest cluster", err)
	log.Printf("DEST CLUSTER   | name=%s | ontap=%s",
		ontapclient.NestedStr(dstCluster, "name"),
		ontapclient.NestedStr(dstCluster, "version", "full"))

	peerResp, err := dst.Get(ctx, "/cluster/peers", map[string]string{
		"fields":       "name,status.state",
		"status.state": "available",
		"max_records":  "1",
	})
	dieOnErr("get cluster peers", err)
	peerName := ""
	if peers := ontapclient.Records(peerResp); len(peers) > 0 {
		peerName = ontapclient.NestedStr(peers[0], "name")
	}
	if peerName == "" {
		log.Fatal("ABORTED — no available cluster peer found on destination cluster; run snapmirror_peer_setup first")
	}
	log.Printf("CLUSTER PEER   | name=%s", peerName)

	aggrResp, err := dst.Get(ctx, "/storage/aggregates", map[string]string{
		"fields":      "name,space.block_storage.available",
		"state":       "online",
		"max_records": "1",
		"order_by":    "space.block_storage.available desc",
	})
	dieOnErr("get dest aggregates", err)
	aggrName := ""
	if aggrs := ontapclient.Records(aggrResp); len(aggrs) > 0 {
		aggrName = ontapclient.NestedStr(aggrs[0], "name")
	}
	if aggrName == "" {
		log.Fatal("ABORTED — no online aggregates found on destination cluster")
	}
	log.Printf("DEST AGGREGATE | name=%s", aggrName)
	return peerName, aggrName
}

// smSrcPhaseC ensures the dest DP volume exists, creating it if needed.
func smSrcPhaseC(ctx context.Context, dst *ontapclient.Client, destSVM, destVolume, aggrName string, srcVolSize int64) {
	checkDest, err := dst.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid,state,type",
		"max_records":          "1",
		"name":                 destVolume,
		ontapclient.KeySVMName: destSVM,
	})
	dieOnErr("check dest volume", err)
	if ontapclient.NumRecords(checkDest) == 0 {
		log.Printf("Creating dest DP volume '%s' on '%s'…", destVolume, aggrName)
		_, err = dst.Post(ctx, ontapclient.PathStorageVolumes, map[string]string{"return_timeout": "120"}, map[string]interface{}{
			"name": destVolume,
			"type": "dp",
			"svm":  map[string]string{"name": destSVM},
			"aggregates": []map[string]string{
				{"name": aggrName},
			},
			"size": srcVolSize,
		})
		if err != nil {
			var apiErr *ontapclient.OntapApiError
			if errors.As(err, &apiErr) && apiErr.ErrorCode() == "917927" {
				log.Printf("create_dest_volume — volume already exists, skipping")
			} else {
				log.Fatalf("create_dest_volume: %v", err)
			}
		}
	} else {
		log.Printf("Dest volume '%s' already exists — skipping create", destVolume)
	}

	dstVolResp, err := dst.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid,state,type",
		"max_records":          "1",
		"name":                 destVolume,
		ontapclient.KeySVMName: destSVM,
	})
	dieOnErr("verify dest volume", err)
	vols := ontapclient.Records(dstVolResp)
	if len(vols) == 0 {
		log.Fatalf("ABORTED — dest volume '%s' not found on SVM '%s' after create", destVolume, destSVM)
	}
	dstVol := vols[0]
	log.Printf("DEST VOLUME    | name=%s | uuid=%s | state=%s | type=%s",
		ontapclient.NestedStr(dstVol, "name"),
		ontapclient.NestedStr(dstVol, "uuid"),
		ontapclient.NestedStr(dstVol, "state"),
		ontapclient.NestedStr(dstVol, "type"))
}

// smSrcPhaseD creates and initializes the SnapMirror relationship; returns the relationship UUID.
func smSrcPhaseD(ctx context.Context, dst *ontapclient.Client, cfg smRelConfig) string {
	existing, err := dst.Get(ctx, pathSMRelationships, map[string]string{
		"fields":           "uuid,state,healthy",
		"destination.path": cfg.destSVM + ":" + cfg.destVolume,
		"max_records":      "1",
	})
	dieOnErr("check existing relationship", err)

	if ontapclient.NumRecords(existing) == 0 {
		createResp, err := dst.Post(ctx, pathSMRelationships, map[string]string{"return_timeout": "120"}, map[string]interface{}{
			"source": map[string]interface{}{
				"path":    cfg.sourceSVM + ":" + cfg.sourceVolume,
				"cluster": map[string]string{"name": cfg.peerName},
			},
			"destination": map[string]string{"path": cfg.destSVM + ":" + cfg.destVolume},
			"policy":      map[string]string{"name": cfg.smPolicy},
		})
		if err != nil {
			log.Fatalf("create_and_initialize_relationship: %v", err)
		}
		if jobUUID := ontapclient.JobUUID(createResp); jobUUID != "" {
			if _, err := dst.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
				log.Printf("poll create job — %v", err)
			}
		}
		log.Println("RELATIONSHIP   | created")
	} else {
		log.Println("RELATIONSHIP   | already exists — skipping create")
	}

	relResp, err := dst.Get(ctx, pathSMRelationships, map[string]string{
		"fields":           "uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
		"destination.path": cfg.destSVM + ":" + cfg.destVolume,
		"max_records":      "1",
	})
	dieOnErr("get relationship", err)
	rels := ontapclient.Records(relResp)
	if len(rels) == 0 {
		log.Fatalf("ABORTED — SnapMirror relationship not found for '%s:%s'", cfg.destSVM, cfg.destVolume)
	}
	rel := rels[0]
	relUUID := ontapclient.NestedStr(rel, "uuid")
	log.Printf("RELATIONSHIP FOUND | uuid=%s | state=%s | healthy=%v",
		relUUID, ontapclient.NestedStr(rel, "state"), rel["healthy"])

	srcInitTransfer(ctx, dst, relUUID)
	return relUUID
}

// srcInitTransfer posts the initial transfer for a SnapMirror relationship and
// handles expected error codes (duplicate, in-progress, LIF connectivity).
func srcInitTransfer(ctx context.Context, dst *ontapclient.Client, relUUID string) {
	_, err := dst.Post(ctx, fmt.Sprintf("%s/%s/transfers", pathSMRelationships, relUUID),
		map[string]string{"return_timeout": "120"}, map[string]interface{}{})
	if err == nil {
		return
	}
	var apiErr *ontapclient.OntapApiError
	if errors.As(err, &apiErr) {
		switch apiErr.ErrorCode() {
		case "13303812":
			log.Fatalf("ABORTED — SnapMirror initialize failed: intercluster LIF connectivity issue.\n"+
				"  Error : %v\n"+
				"  Cause : TCP ports 11104/11105 are likely blocked between the source and dest IC LIFs.",
				err)
		case "917927", "13303809": // already exists / transfer already in progress
			log.Printf("initialize_relationship — already initialized or in progress (code %s)", apiErr.ErrorCode())
		default:
			log.Fatalf("initialize_relationship failed (code=%s): %v", apiErr.ErrorCode(), err)
		}
	} else {
		log.Fatalf("initialize_relationship failed (network error): %v", err)
	}
}

// smSrcPhaseF prints the final validation report.
func smSrcPhaseF(ctx context.Context, dst *ontapclient.Client, relUUID, sourceSVM, sourceVolume, destSVM, destVolume string) {
	final, err := dst.Get(ctx, fmt.Sprintf(pathSMRelationships+"/%s", relUUID),
		map[string]string{"fields": "uuid,source.path,destination.path,state,lag_time,healthy,policy.name"})
	dieOnErr("final validation", err)
	log.Printf("=== SNAPMIRROR PROVISION COMPLETE ===\n"+
		"  source      : %s:%s\n"+
		"  destination : %s:%s\n"+
		"  state       : %s\n"+
		"  healthy     : %v\n"+
		"  policy      : %s\n"+
		"  lag_time    : %v",
		sourceSVM, sourceVolume,
		destSVM, destVolume,
		ontapclient.NestedStr(final, "state"),
		final["healthy"],
		ontapclient.NestedStr(final, "policy", "name"),
		final["lag_time"])
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
