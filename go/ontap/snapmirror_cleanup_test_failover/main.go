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
//  1. Go 1.22+ installed; run `cd go && go mod download` once to cache deps
//  2. ONTAP 9.8+ on both clusters
//  3. snapmirror_test_failover.go must have been run first
//  4. The SnapMirror relationship must still be accessible on one of the clusters
//  5. Admin credentials for both clusters
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
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	ontapclient "github.com/netapp/pace/go/ontap/ontapclient"
)

const (
	volumeOpPathFmt     = ontapclient.PathStorageVolumes + "/%s"
	pathSMRelationships = "/snapmirror/relationships"
)

// ---------------------------------------------------------------------------

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	clusterA := mustEnv("CLUSTER_A")
	clusterB := mustEnv("CLUSTER_B")
	destUser := envOrDefault("DEST_USER", "admin")
	destPass := mustEnv("DEST_PASS")
	sourceVolume := mustEnv("SOURCE_VOLUME")
	sourceSVM := mustEnv("SOURCE_SVM")

	// === Phase 0: Find SnapMirror relationship ===
	log.Println("=== Phase 0: Find SnapMirror relationship ===")
	destHost, rel := pickClusterByRelationship(ctx, clusterA, clusterB, destUser, destPass, sourceSVM, sourceVolume)
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
	clone, findErr := findTaggedClone(ctx, client, relUUID)
	if findErr != nil {
		log.Fatalf("find tagged clone: %v", findErr)
	}
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

	removeSMASRelationships(ctx, client, cloneSVM, cloneName)
	unmountClone(ctx, client, cloneUUID)
	offlineClone(ctx, client, cloneUUID)
	deleteAndConfirmClone(ctx, client, cloneUUID, cloneName, destHost)
}

// pickClusterByRelationship returns (clusterIP, relationshipRecord) for the cluster owning this SM rel.
func pickClusterByRelationship(ctx context.Context, clusterA, clusterB, user, passwd, sourceSVM, sourceVolume string) (string, map[string]interface{}) {
	sourcePath := sourceSVM + ":" + sourceVolume
	tryHost := func(host string) (map[string]interface{}, bool) {
		c := ontapclient.New(host, user, passwd, false)
		defer c.Close()
		resp, err := c.Get(ctx, pathSMRelationships, map[string]string{
			"fields":      "uuid,source.path,destination.path,state,healthy",
			"source.path": sourcePath,
			"max_records": "1",
		})
		if err != nil {
			log.Printf("  cluster %s — %v", host, err)
			return nil, false
		}
		if ontapclient.NumRecords(resp) >= 1 {
			return ontapclient.Records(resp)[0], true
		}
		return nil, false
	}
	for _, host := range []string{clusterA, clusterB} {
		if rel, ok := tryHost(host); ok {
			return host, rel
		}
	}
	log.Fatalf("No SM relationship found for %s on either cluster (%s, %s)", sourcePath, clusterA, clusterB)
	return "", nil
}

// findTaggedClone returns the clone tagged '<relUUID>:test', or (nil, nil) if not found.
// Returns a non-nil error if the API call itself fails (e.g. auth error, network failure),
// distinguishing a genuine "nothing to clean up" from a broken connection.
func findTaggedClone(ctx context.Context, client *ontapclient.Client, relUUID string) (map[string]interface{}, error) {
	resp, err := client.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":      "name,uuid,svm.name,state,nas.path",
		"_tags":       relUUID + ":test",
		"max_records": "1",
	})
	if err != nil {
		return nil, fmt.Errorf("find tagged clone: %w", err)
	}
	if ontapclient.NumRecords(resp) == 0 {
		return nil, nil
	}
	rec := ontapclient.Records(resp)[0]
	return map[string]interface{}{
		"uuid": ontapclient.NestedStr(rec, "uuid"),
		"name": ontapclient.NestedStr(rec, "name"),
		"svm":  ontapclient.NestedStr(rec, "svm", "name"),
	}, nil
}

// removeSMASRelationships deletes any SMAS SnapMirror relationships on the clone volume.
func removeSMASRelationships(ctx context.Context, client *ontapclient.Client, cloneSVM, cloneName string) {
	log.Println("=== Phase B: Remove SMAS relationship on clone (if any) ===")
	smasResp, err := client.Get(ctx, pathSMRelationships, map[string]string{
		"fields":           "uuid,state",
		"destination.path": cloneSVM + ":" + cloneName,
		"max_records":      "10",
	})
	if err != nil {
		log.Fatalf("list smas relationships: %v", err)
	}
	smasRels := ontapclient.Records(smasResp)
	for _, r := range smasRels {
		smasUUID := ontapclient.NestedStr(r, "uuid")
		log.Printf("  Deleting SMAS relationship %s on clone", smasUUID)
		resp, err := client.Delete(ctx, fmt.Sprintf(pathSMRelationships+"/%s", smasUUID),
			map[string]string{"return_timeout": "120", "force": "true"})
		if err != nil {
			log.Printf("delete_smas_rel %s — %v (continuing)", smasUUID, err)
			continue
		}
		if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
			if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
				log.Printf("poll delete smas job — %v", err)
			}
		}
	}
	if len(smasRels) == 0 {
		log.Println("  No SMAS relationships found on clone — continuing")
	}
}

// unmountClone removes the NAS junction path; retries up to 6 times before aborting.
func unmountClone(ctx context.Context, client *ontapclient.Client, cloneUUID string) {
	log.Println("=== Phase C: Unmount clone ===")
	for attempt := 1; attempt <= 6; attempt++ {
		resp, err := client.Patch(ctx, fmt.Sprintf(volumeOpPathFmt, cloneUUID),
			map[string]string{"return_timeout": "120"},
			map[string]interface{}{"nas": map[string]string{"path": ""}})
		if err != nil {
			log.Printf("unmount_clone attempt %d/6 — %v", attempt, err)
			if attempt < 6 {
				select {
				case <-ctx.Done():
					log.Fatalf("unmount_clone: context cancelled — %v", ctx.Err())
				case <-time.After(10 * time.Second):
				}
			}
			continue
		}
		if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
			if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
				log.Printf("poll unmount job — %v", err)
			}
		}
		return
	}
	log.Fatal("Failed to unmount clone after 6 attempts — aborting")
}

// offlineClone sets the volume state to offline (required before delete).
func offlineClone(ctx context.Context, client *ontapclient.Client, cloneUUID string) {
	log.Println("=== Phase D: Offline clone ===")
	resp, err := client.Patch(ctx, fmt.Sprintf(volumeOpPathFmt, cloneUUID),
		map[string]string{"return_timeout": "120"},
		map[string]interface{}{"state": "offline"})
	if err != nil {
		log.Printf("offline_clone — %v", err)
		return
	}
	if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Printf("poll offline job — %v", err)
		}
	}
}

// deleteAndConfirmClone deletes the clone volume and confirms it is gone.
// The confirmation GET is the single source of truth: if the volume is already
// absent when the delete call errors, the function reports success rather than fataling.
func deleteAndConfirmClone(ctx context.Context, client *ontapclient.Client, cloneUUID, cloneName, destHost string) {
	log.Println("=== Phase E: Delete clone ===")
	resp, err := client.Delete(ctx, fmt.Sprintf(volumeOpPathFmt, cloneUUID), map[string]string{"return_timeout": "120"})
	if err != nil {
		// Volume may already be gone — confirm via direct path GET before declaring failure.
		_, cErr := client.Get(ctx, fmt.Sprintf(volumeOpPathFmt, cloneUUID), nil)
		if isNotFound(cErr) {
			log.Printf("=== CLEANUP COMPLETE — clone '%s' already removed from cluster %s ===", cloneName, destHost)
			return
		}
		log.Fatalf("delete_clone: %v", err)
	}
	if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Printf("poll delete job — %v", err)
		}
	}

	_, cErr := client.Get(ctx, fmt.Sprintf(volumeOpPathFmt, cloneUUID), nil)
	if isNotFound(cErr) {
		log.Printf("=== CLEANUP COMPLETE — clone '%s' deleted from cluster %s ===", cloneName, destHost)
	} else {
		log.Fatalf("Clone '%s' still exists after delete attempt", cloneName)
	}
}

// isNotFound reports whether err is an ONTAP 404 Not Found response.
func isNotFound(err error) bool {
	var apiErr *ontapclient.OntapApiError
	return errors.As(err, &apiErr) && apiErr.StatusCode == 404
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
