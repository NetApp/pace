// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// SnapMirror Test Failover — creates a writable FlexClone of a SnapMirror dest volume.
//
// AUTO mode  (SOURCE_VOLUME=* or unset):
//
//	Queries clusters A then B and selects the first cluster that has a matching DP volume
//	(the newest matching DP volume within that cluster).
//
// TARGETED mode (SOURCE_VOLUME=vol_rw_01):
//
//	Finds vol_rw_01_dest on either cluster.
//
// Phases:
//
//	0  Auto-detect which cluster has the target DP volume
//	A  Pre-flight  — verify cluster + relationship health
//	B  Snapshot    — get latest SnapMirror snapshot on dest volume
//	C  Clone       — create writable FlexClone
//	D  Verify      — confirm clone online + tag with SM relationship UUID
//	E  Resync      — resync SnapMirror + validate healthy state
//
// Prerequisites:
//  1. ONTAP 9.8+ on both clusters
//  2. A healthy SnapMirror relationship must already exist
//  3. Relationship state must be 'snapmirrored' (baseline transfer complete)
//  4. At least one SnapMirror snapshot on the destination volume
//  5. Admin credentials for both clusters
//
// Usage:
//
//	export CLUSTER_A=10.x.x.x  CLUSTER_B=10.y.y.y
//	export DEST_USER=admin      DEST_PASS=secret
//	export SOURCE_VOLUME=*      # or a specific volume name e.g. "vol_rw_01"
//	go run .
package main

import (
	"fmt"
	"log"
	"os"
	"strings"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

const pathStorageVolumes = "/storage/volumes" // NOSONAR

// ---------------------------------------------------------------------------

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()

	clusterA := mustEnv("CLUSTER_A")
	clusterB := mustEnv("CLUSTER_B")
	destUser := envOrDefault("DEST_USER", "admin")
	destPass := mustEnv("DEST_PASS")
	sourceVolume := envOrDefault("SOURCE_VOLUME", "*")

	log.Println("=== Phase 0: Auto-detect target cluster ===")
	destHost, dpVol := pickCluster(clusterA, clusterB, destUser, destPass, sourceVolume)
	dpVolName := ontapclient.NestedStr(dpVol, "name")
	dpSVMName := ontapclient.NestedStr(dpVol, "svm", "name")
	dpVolUUID := ontapclient.NestedStr(dpVol, "uuid")
	log.Printf("SELECTED | cluster=%s | volume=%s | svm=%s | uuid=%s | state=%s | size=%.0f",
		destHost, dpVolName, dpSVMName, dpVolUUID,
		ontapclient.NestedStr(dpVol, "state"),
		ontapclient.NestedFloat(dpVol, "space", "size"))

	client := ontapclient.New(destHost, destUser, destPass, false)
	defer client.Close()

	log.Println("=== Phase A: Pre-flight ===")
	relUUID := tfPhaseA(client, dpSVMName, dpVolName)

	log.Println("=== Phase B: Get latest SnapMirror snapshot ===")
	snapshotName := tfPhaseB(client, dpVolUUID, dpVolName)

	log.Println("=== Phase C: Create FlexClone ===")
	cloneName, cloneUUID := tfPhaseC(client, dpVolName, dpSVMName, snapshotName)

	log.Println("=== Phase D: Verify clone + tag ===")
	tfPhaseD(client, cloneName, cloneUUID, relUUID, dpSVMName, snapshotName)

	log.Println("=== Phase E: Resync SnapMirror ===")
	tfPhaseE(client, relUUID)
}

// tfPhaseA verifies cluster connectivity and fetches the SnapMirror relationship UUID.
func tfPhaseA(client *ontapclient.Client, dpSVMName, dpVolName string) string {
	cluster, err := client.Get("/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get cluster", err)
	log.Printf("DEST CLUSTER | name=%s | ontap=%s",
		ontapclient.NestedStr(cluster, "name"),
		ontapclient.NestedStr(cluster, "version", "full"))

	relResp, err := client.Get("/snapmirror/relationships", map[string]string{
		"fields":           "uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
		"destination.path": dpSVMName + ":" + dpVolName,
		"max_records":      "1",
	})
	dieOnErr("get snapmirror relationship", err)
	rels := ontapclient.Records(relResp)
	if len(rels) == 0 {
		log.Fatalf("No SnapMirror relationship found for %s:%s", dpSVMName, dpVolName)
	}
	rel := rels[0]
	relUUID := ontapclient.NestedStr(rel, "uuid")
	log.Printf("RELATIONSHIP | uuid=%s | source=%s | dest=%s | state=%s | healthy=%v | lag=%v",
		relUUID,
		ontapclient.NestedStr(rel, "source", "path"),
		ontapclient.NestedStr(rel, "destination", "path"),
		ontapclient.NestedStr(rel, "state"),
		rel["healthy"], rel["lag_time"])
	return relUUID
}

// tfPhaseB fetches the latest SnapMirror snapshot name from the DP volume.
func tfPhaseB(client *ontapclient.Client, dpVolUUID, dpVolName string) string {
	snapResp, err := client.Get(fmt.Sprintf("/storage/volumes/%s/snapshots", dpVolUUID), map[string]string{
		"fields":      "name,create_time",
		"max_records": "1",
		"order_by":    "create_time desc",
	})
	dieOnErr("get snapshots", err)
	if ontapclient.NumRecords(snapResp) == 0 {
		log.Fatalf("No SnapMirror snapshots on %s — run provision workflow first", dpVolName)
	}
	snap := ontapclient.Records(snapResp)[0]
	snapshotName := ontapclient.NestedStr(snap, "name")
	log.Printf("LATEST SM SNAPSHOT | name=%s | created=%v", snapshotName, snap["create_time"])
	return snapshotName
}

// tfPhaseC creates the writable FlexClone; returns (cloneName, cloneUUID).
func tfPhaseC(client *ontapclient.Client, dpVolName, dpSVMName, snapshotName string) (string, string) {
	cloneName := dpVolName + "_clone"
	cloneResp, err := client.Post("/storage/volumes?return_timeout=120", map[string]interface{}{
		"name": cloneName,
		"svm":  map[string]string{"name": dpSVMName},
		"nas":  map[string]string{"path": "/" + cloneName},
		"clone": map[string]interface{}{
			"is_flexclone":    true,
			"parent_volume":   map[string]string{"name": dpVolName},
			"parent_snapshot": map[string]string{"name": snapshotName},
		},
	})
	if err != nil {
		log.Printf("create_test_clone — %v (may already exist)", err)
	} else if jobUUID := ontapclient.JobUUID(cloneResp); jobUUID != "" {
		if _, err := client.PollJob(jobUUID, 10); err != nil {
			log.Printf("poll clone job — %v", err)
		}
	}

	cloneVolResp, err := client.Get(pathStorageVolumes, map[string]string{
		"fields":      "name,uuid,state,nas.path,space.size",
		"max_records": "1",
		"name":        cloneName,
		"svm.name":    dpSVMName,
	})
	dieOnErr("get clone volume", err)
	cloneVol := map[string]interface{}{}
	if vols := ontapclient.Records(cloneVolResp); len(vols) > 0 {
		cloneVol = vols[0]
	}
	cloneUUID := ontapclient.NestedStr(cloneVol, "uuid")
	if cloneUUID == "" {
		log.Fatalf("ABORTED — FlexClone '%s' not found after create (create may have failed)", cloneName)
	}
	log.Printf("CLONE | name=%s | uuid=%s | state=%s | junction=%s",
		ontapclient.NestedStr(cloneVol, "name"), cloneUUID,
		ontapclient.NestedStr(cloneVol, "state"),
		ontapclient.NestedStr(cloneVol, "nas", "path"))
	return cloneName, cloneUUID
}

// tfPhaseD tags the clone and prints the test-failover-ready message.
func tfPhaseD(client *ontapclient.Client, cloneName, cloneUUID, relUUID, dpSVMName, snapshotName string) {
	_, err := client.Patch(fmt.Sprintf("/storage/volumes/%s?return_timeout=120", cloneUUID),
		map[string]interface{}{"_tags": []string{relUUID + ":test"}})
	if err != nil {
		log.Printf("tag_clone_volume — %v", err)
	} else {
		log.Printf("TAG APPLIED | clone=%s | tag=%s:test", cloneName, relUUID)
	}

	cloneVolResp, err := client.Get(pathStorageVolumes, map[string]string{
		"fields":      "name,uuid,state,nas.path",
		"max_records": "1",
		"name":        cloneName,
		"svm.name":    dpSVMName,
	})
	if err != nil {
		log.Printf("re-fetch clone — %v", err)
		return
	}
	cloneVol := map[string]interface{}{}
	if vols := ontapclient.Records(cloneVolResp); len(vols) > 0 {
		cloneVol = vols[0]
	}
	junctionPath := ontapclient.NestedStr(cloneVol, "nas", "path")
	log.Printf("=== TEST FAILOVER READY ===\n"+
		"  Clone    : %s\n  UUID     : %s\n  State    : %s\n"+
		"  Junction : %s\n  SVM      : %s\n  Snapshot : %s\n\n"+
		"  ACTION: Mount %s from SVM %s on a test client.",
		ontapclient.NestedStr(cloneVol, "name"), cloneUUID,
		ontapclient.NestedStr(cloneVol, "state"),
		junctionPath, dpSVMName, snapshotName,
		junctionPath, dpSVMName)
}

// tfPhaseE resyncs the SnapMirror relationship and waits for snapmirrored state.
func tfPhaseE(client *ontapclient.Client, relUUID string) {
	resyncResp, err := client.Patch(fmt.Sprintf("/snapmirror/relationships/%s?return_timeout=120", relUUID),
		map[string]interface{}{"state": "snapmirrored"})
	if err != nil {
		log.Printf("resync_sm_relationship — %v", err)
	} else if jobUUID := ontapclient.JobUUID(resyncResp); jobUUID != "" {
		if _, err := client.PollJob(jobUUID, 10); err != nil {
			log.Printf("poll resync job — %v", err)
		}
	}
	if _, err := client.WaitSnapmirrored(relUUID, 15, 1800); err != nil {
		log.Fatalf("wait snapmirrored: %v", err)
	}
	log.Println("=== TEST FAILOVER COMPLETE — SnapMirror resynced ===")
}

// pickCluster finds which cluster has the target DP volume; returns (clusterIP, volRecord).
func pickCluster(clusterA, clusterB, user, passwd, volNameFilter string) (string, map[string]interface{}) {
	destFilter := volNameFilter + "_dest"
	if volNameFilter == "*" {
		destFilter = "*_dest"
	}
	for _, host := range []string{clusterA, clusterB} {
		client := ontapclient.New(host, user, passwd, false)
		resp, err := client.Get(pathStorageVolumes, map[string]string{
			"fields":      "name,create_time,uuid,svm.name,state,space.size",
			"type":        "dp",
			"name":        destFilter,
			"order_by":    "create_time desc",
			"max_records": "1",
		})
		client.Close()
		if err != nil {
			log.Printf("  cluster %s — %v", host, err)
			continue
		}
		if ontapclient.NumRecords(resp) >= 1 {
			return host, ontapclient.Records(resp)[0]
		}
	}
	log.Fatalf("No DP volumes found on either cluster (%s, %s)", clusterA, clusterB)
	return "", nil
}

func mustEnv(key string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	log.Fatalf("'%s' is required — set it in go/.env or as an environment variable", key)
	return ""
}

func envOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func dieOnErr(context string, err error) {
	if err != nil {
		log.Fatalf("%s: %v", context, err)
	}
}

// loadDotEnv reads a .env file from the current directory and exports each
// KEY=VALUE pair as an environment variable (only if not already set).
// The file is gitignored — safe to store credentials there for local testing.
func loadDotEnv() {
	data, err := os.ReadFile(".env")
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		if os.Getenv(strings.TrimSpace(k)) == "" {
			_ = os.Setenv(strings.TrimSpace(k), strings.TrimSpace(v))
		}
	}
}
