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
//  1. ONTAP 9.8+ on both clusters
//  2. SnapMirror licence installed on both clusters
//  3. At least one intercluster LIF on each cluster
//  4. Cluster peer relationship already exists between source and dest clusters
//  5. SVM peer relationship already exists (source SVM <-> dest SVM)
//  6. Source RW volume (SOURCE_VOLUME) already exists on SOURCE_SVM
//  7. At least one online aggregate on the destination cluster
//  8. Admin credentials for both clusters
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

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

// ---------------------------------------------------------------------------

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

	destVolume := sourceVolume + "_dest"

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
	relUUID := smSrcPhaseD(ctx, dst, sourceSVM, sourceVolume, destSVM, destVolume, peerName, smPolicy)

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
func smSrcPhaseD(ctx context.Context, dst *ontapclient.Client, sourceSVM, sourceVolume, destSVM, destVolume, peerName, smPolicy string) string {
	existing, err := dst.Get(ctx, "/snapmirror/relationships", map[string]string{
		"fields":           "uuid,state,healthy",
		"destination.path": destSVM + ":" + destVolume,
		"max_records":      "1",
	})
	dieOnErr("check existing relationship", err)

	if ontapclient.NumRecords(existing) == 0 {
		createResp, err := dst.Post(ctx, "/snapmirror/relationships", map[string]string{"return_timeout": "120"}, map[string]interface{}{
			"source": map[string]interface{}{
				"path":    sourceSVM + ":" + sourceVolume,
				"cluster": map[string]string{"name": peerName},
			},
			"destination": map[string]string{"path": destSVM + ":" + destVolume},
			"policy":      map[string]string{"name": smPolicy},
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

	relResp, err := dst.Get(ctx, "/snapmirror/relationships", map[string]string{
		"fields":           "uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
		"destination.path": destSVM + ":" + destVolume,
		"max_records":      "1",
	})
	dieOnErr("get relationship", err)
	rels := ontapclient.Records(relResp)
	if len(rels) == 0 {
		log.Fatalf("ABORTED — SnapMirror relationship not found for '%s:%s'", destSVM, destVolume)
	}
	rel := rels[0]
	relUUID := ontapclient.NestedStr(rel, "uuid")
	log.Printf("RELATIONSHIP FOUND | uuid=%s | state=%s | healthy=%v",
		relUUID, ontapclient.NestedStr(rel, "state"), rel["healthy"])

	_, err = dst.Post(ctx, fmt.Sprintf("/snapmirror/relationships/%s/transfers", relUUID), map[string]string{"return_timeout": "120"}, map[string]interface{}{})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if errors.As(err, &apiErr) && apiErr.ErrorCode() == "13303812" {
			log.Fatalf("ABORTED — SnapMirror initialize failed: intercluster LIF connectivity issue.\n"+
				"  Error : %v\n"+
				"  Cause : TCP ports 11104/11105 are likely blocked between the source and dest IC LIFs.",
				err)
		}
		log.Printf("initialize_relationship — %v (may already be initialized)", err)
	}
	return relUUID
}

// smSrcPhaseF prints the final validation report.
func smSrcPhaseF(ctx context.Context, dst *ontapclient.Client, relUUID, sourceSVM, sourceVolume, destSVM, destVolume string) {
	final, err := dst.Get(ctx, fmt.Sprintf("/snapmirror/relationships/%s", relUUID),
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
