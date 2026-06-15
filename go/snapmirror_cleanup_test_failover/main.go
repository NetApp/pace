// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// SnapMirror Test Failover Cleanup — deletes the FlexClone created by test_failover.
//
// Finds the clone via SnapMirror relationship UUID tag ("<uuid>:test").
// Only clones tagged by the snapmirror_test_failover workflow are touched — manually
// created volumes are never matched or deleted.
//
// Phases:
//
//	0  Relationship-pick  — find SM relationship on correct cluster
//	A  Tag-based find     — locate clone tagged with "<uuid>:test"
//	B  SMAS removal       — delete any SMAS relationship on the clone (releases lock)
//	C  Unmount            — remove NAS junction path (with retry)
//	D  Offline            — set volume state to offline
//	E  Delete             — delete the clone and confirm removal
//
// Prerequisites:
//  1. ONTAP 9.8+ on both clusters
//  2. snapmirror_test_failover.go must have been run first
//  3. The SnapMirror relationship must still be accessible on one of the clusters
//  4. Admin credentials for both clusters
//
// Usage:
//
//	export CLUSTER_A=10.x.x.x   CLUSTER_B=10.y.y.y
//	export DEST_USER=admin       DEST_PASS=secret
//	export SOURCE_VOLUME=vol_rw_01
//	export SOURCE_SVM=vs0
//	go run .
package main

import (
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

const volumePatchPath = "/storage/volumes/%s?return_timeout=120"

// ---------------------------------------------------------------------------

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()

	clusterA := mustEnv("CLUSTER_A")
	clusterB := mustEnv("CLUSTER_B")
	destUser := envOrDefault("DEST_USER", "admin")
	destPass := mustEnv("DEST_PASS")
	sourceVolume := mustEnv("SOURCE_VOLUME")
	sourceSVM := mustEnv("SOURCE_SVM")

	// === Phase 0: Find SnapMirror relationship ===
	log.Println("=== Phase 0: Find SnapMirror relationship ===")
	destHost, rel := pickClusterByRelationship(clusterA, clusterB, destUser, destPass, sourceSVM, sourceVolume)
	relUUID := ontapclient.NestedStr(rel, "uuid")
	log.Printf("RELATIONSHIP FOUND | cluster=%s | uuid=%s | source=%s | dest=%s | state=%s | healthy=%v",
		destHost,
		relUUID,
		ontapclient.NestedStr(rel, "source", "path"),
		ontapclient.NestedStr(rel, "destination", "path"),
		ontapclient.NestedStr(rel, "state"),
		rel["healthy"])

	if ontapclient.NestedStr(rel, "state") != "snapmirrored" {
		log.Printf("Relationship state=%s healthy=%v — proceeding with cleanup anyway",
			ontapclient.NestedStr(rel, "state"), rel["healthy"])
	}

	client := ontapclient.New(destHost, destUser, destPass, false)
	defer client.Close()

	// === Phase A: Find tagged clone ===
	log.Println("=== Phase A: Find tagged clone ===")
	clone := findTaggedClone(client, relUUID)
	if clone == nil {
		log.Printf("NO TAGGED CLONE FOUND for %s:%s on %s — nothing to clean up",
			sourceSVM, sourceVolume, destHost)
		return
	}
	log.Printf("CLONE FOUND | name=%s | uuid=%s | svm=%s | cluster=%s",
		clone["name"], clone["uuid"], clone["svm"], destHost)

	cloneUUID, _ := clone["uuid"].(string)
	cloneSVM, _ := clone["svm"].(string)
	cloneName, _ := clone["name"].(string)

	removeSMASAndBringOnline(client, cloneUUID, cloneSVM, cloneName)
	unmountClone(client, cloneUUID)
	offlineClone(client, cloneUUID)
	deleteAndConfirmClone(client, cloneUUID, cloneName, destHost)
}

// pickClusterByRelationship returns (clusterIP, relationshipRecord) for the cluster owning this SM rel.
func pickClusterByRelationship(clusterA, clusterB, user, passwd, sourceSVM, sourceVolume string) (string, map[string]interface{}) {
	sourcePath := sourceSVM + ":" + sourceVolume
	for _, host := range []string{clusterA, clusterB} {
		client := ontapclient.New(host, user, passwd, false)
		resp, err := client.Get("/snapmirror/relationships", map[string]string{
			"fields":      "uuid,source.path,destination.path,state,healthy",
			"source.path": sourcePath,
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
	log.Fatalf("No SM relationship found for %s on either cluster (%s, %s)", sourcePath, clusterA, clusterB)
	return "", nil
}

// findTaggedClone returns the clone tagged '<relUUID>:test', or nil if not found.
func findTaggedClone(client *ontapclient.Client, relUUID string) map[string]interface{} {
	resp, err := client.Get("/storage/volumes", map[string]string{
		"fields":      "name,uuid,svm.name,state,nas.path",
		"_tags":       relUUID + ":test",
		"max_records": "1",
	})
	if err != nil || ontapclient.NumRecords(resp) == 0 {
		return nil
	}
	rec := ontapclient.Records(resp)[0]
	return map[string]interface{}{
		"uuid": ontapclient.NestedStr(rec, "uuid"),
		"name": ontapclient.NestedStr(rec, "name"),
		"svm":  ontapclient.NestedStr(rec, "svm", "name"),
	}
}

// removeSMASAndBringOnline deletes any SMAS relationship on the clone, then ensures it is online.
func removeSMASAndBringOnline(client *ontapclient.Client, cloneUUID, cloneSVM, cloneName string) {
	log.Println("=== Phase B: Remove SMAS relationship on clone (if any) ===")
	smasResp, err := client.Get("/snapmirror/relationships", map[string]string{
		"fields":           "uuid,state",
		"destination.path": cloneSVM + ":" + cloneName,
		"max_records":      "10",
	})
	if err != nil {
		log.Printf("list smas relationships: %v (continuing)", err)
	}
	smasRels := ontapclient.Records(smasResp)
	for _, r := range smasRels {
		smasUUID := ontapclient.NestedStr(r, "uuid")
		log.Printf("  Deleting SMAS relationship %s on clone", smasUUID)
		resp, err := client.Delete(fmt.Sprintf("/snapmirror/relationships/%s?return_timeout=120&force=true", smasUUID))
		if err != nil {
			log.Printf("delete_smas_rel %s — %v (continuing)", smasUUID, err)
			continue
		}
		if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
			if _, err := client.PollJob(jobUUID, 10); err != nil {
				log.Printf("poll delete smas job — %v", err)
			}
		}
	}
	if len(smasRels) == 0 {
		log.Println("  No SMAS relationships found on clone — continuing")
	}

	resp, err := client.Patch(fmt.Sprintf(volumePatchPath, cloneUUID),
		map[string]interface{}{"state": "online"})
	if err != nil {
		log.Printf("bring_online — %v (continuing)", err)
		return
	}
	if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := client.PollJob(jobUUID, 10); err != nil {
			log.Printf("poll bring-online job — %v", err)
		}
	}
}

// unmountClone removes the NAS junction path; retries up to 6 times before aborting.
func unmountClone(client *ontapclient.Client, cloneUUID string) {
	log.Println("=== Phase C: Unmount clone ===")
	for attempt := 1; attempt <= 6; attempt++ {
		resp, err := client.Patch(fmt.Sprintf(volumePatchPath, cloneUUID),
			map[string]interface{}{"nas": map[string]string{"path": ""}})
		if err != nil {
			log.Printf("unmount_clone attempt %d/6 — %v", attempt, err)
			if attempt < 6 {
				time.Sleep(10 * time.Second)
			}
			continue
		}
		if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
			if _, err := client.PollJob(jobUUID, 10); err != nil {
				log.Printf("poll unmount job — %v", err)
			}
		}
		return
	}
	log.Fatal("Failed to unmount clone after 6 attempts — aborting")
}

// offlineClone sets the volume state to offline (required before delete).
func offlineClone(client *ontapclient.Client, cloneUUID string) {
	log.Println("=== Phase D: Offline clone ===")
	resp, err := client.Patch(fmt.Sprintf(volumePatchPath, cloneUUID),
		map[string]interface{}{"state": "offline"})
	if err != nil {
		log.Printf("offline_clone — %v", err)
		return
	}
	if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := client.PollJob(jobUUID, 10); err != nil {
			log.Printf("poll offline job — %v", err)
		}
	}
}

// deleteAndConfirmClone deletes the clone volume and confirms it is gone.
func deleteAndConfirmClone(client *ontapclient.Client, cloneUUID, cloneName, destHost string) {
	log.Println("=== Phase E: Delete clone ===")
	resp, err := client.Delete(fmt.Sprintf(volumePatchPath, cloneUUID))
	if err != nil {
		log.Printf("delete_clone — %v", err)
	} else if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := client.PollJob(jobUUID, 10); err != nil {
			log.Printf("poll delete job — %v", err)
		}
	}

	confirm, err := client.Get("/storage/volumes", map[string]string{
		"fields":      "name,uuid",
		"uuid":        cloneUUID,
		"max_records": "1",
	})
	if err != nil || ontapclient.NumRecords(confirm) == 0 {
		log.Printf("=== CLEANUP COMPLETE — clone '%s' deleted from cluster %s ===", cloneName, destHost)
	} else {
		log.Fatalf("Clone '%s' still exists after delete attempt", cloneName)
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
