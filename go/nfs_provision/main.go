// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// NFS Provision — create a FlexVol volume with a dedicated NFS export policy.
//
// Steps:
//
//	0  preflight          — verify cluster connectivity; log cluster name + ONTAP version
//	1  ensureVolume       — create FlexVol if it does not exist; poll creation job
//	2  ensureExportPolicy — create NFS export policy if it does not exist; fetch its ID
//	3  ensureClientRule   — add a client-match rule to the policy (skip if already present)
//	4  assignPolicy       — PATCH the volume to assign the export policy; poll job if async
//	5  summary            — log mount path, export policy name, and client-match subnet
//
// The script is idempotent: re-running with the same parameters skips any step
// that is already complete.
//
// Prerequisites:
//  1. Go 1.22+ installed; run `cd go && go mod download` once to cache deps
//  2. ONTAP 9.8+ cluster with NFS licence enabled on the target SVM
//  3. Target SVM (SVM_NAME) already exists and has NFS configured
//  4. Target aggregate (AGGR_NAME) already online
//
// Usage:
//
//	export ONTAP_HOST=10.x.x.x   ONTAP_USER=admin   ONTAP_PASS=secret
//	export SVM_NAME=vs0
//	export VOLUME_NAME=vol_nfs_test_01
//	export VOLUME_SIZE=100MB
//	export AGGR_NAME=aggr1
//	export CLIENT_MATCH=10.0.0.0/24
//	go run .
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

// pathExportPolicies is the ONTAP REST path for NFS export-policy operations.
const pathExportPolicies = "/protocols/nfs/export-policies"

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	svmName := mustEnv("SVM_NAME")
	volumeName := mustEnv("VOLUME_NAME")
	volumeSize := envOrDefault("VOLUME_SIZE", "100MB")
	aggrName := mustEnv("AGGR_NAME")
	clientMatch := envOrDefault("CLIENT_MATCH", "0.0.0.0/0")

	policyName := volumeName + "_export_policy"

	client, err := ontapclient.FromEnv()
	dieOnErr("init client", err)
	defer client.Close()

	log.Printf("NFS provision starting — SVM=%s | volume=%s | size=%s | aggr=%s",
		svmName, volumeName, volumeSize, aggrName)

	log.Println("=== Step 0: Verify cluster connectivity ===")
	cluster, err := client.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get cluster", err)
	log.Printf("CLUSTER | name=%s | ontap=%s",
		ontapclient.NestedStr(cluster, "name"),
		ontapclient.NestedStr(cluster, "version", "full"))

	log.Println("=== Step 1: Ensure volume ===")
	volumeUUID := ensureVolume(ctx, client, svmName, volumeName, volumeSize, aggrName)

	log.Println("=== Step 2: Ensure export policy ===")
	policyID := ensureExportPolicy(ctx, client, svmName, policyName)

	log.Println("=== Step 3: Ensure client rule ===")
	ensureClientRule(ctx, client, policyID, clientMatch)

	log.Println("=== Step 4: Assign export policy to volume ===")
	assignPolicy(ctx, client, volumeUUID, policyName)

	log.Printf("=== NFS VOLUME PROVISIONED ===\n"+
		"  SVM          : %s\n"+
		"  Volume       : %s\n"+
		"  Mount path   : /%s\n"+
		"  Export policy: %s\n"+
		"  Client match : %s",
		svmName, volumeName, volumeName, policyName, clientMatch)
}

// ensureVolume creates a FlexVol if it does not exist.
// The volume is mounted at /<volume> so NFS clients can access it immediately.
// Returns the volume UUID, which is required by assignPolicy.
func ensureVolume(ctx context.Context, client *ontapclient.Client, svm, volume, size, aggr string) string {
	checkResp, err := client.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid",
		"max_records":          "1",
		"name":                 volume,
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("check volume", err)

	if ontapclient.NumRecords(checkResp) == 0 {
		log.Printf("Creating volume '%s' (%s) on SVM '%s' aggregate '%s'…", volume, size, svm, aggr)
		createResp, err := client.Post(ctx, ontapclient.PathStorageVolumes, nil, map[string]interface{}{
			"name": volume,
			"svm":  map[string]string{"name": svm},
			"aggregates": []map[string]string{
				{"name": aggr},
			},
			"size": size,
			"nas": map[string]string{
				"path": fmt.Sprintf("/%s", volume),
			},
		})
		dieOnErr("create volume", err)

		if jobUUID := ontapclient.NestedStr(createResp, "job", "uuid"); jobUUID != "" {
			log.Printf("  volume creation job: %s", jobUUID)
			if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
				log.Fatalf("volume creation job failed: %v", err)
			}
		}
		log.Printf("Volume '%s' created successfully", volume)
	} else {
		log.Printf("Volume '%s' already exists — skipping create", volume)
	}

	// Always fetch the UUID so the return value is valid whether we just created it or not.
	volResp, err := client.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid",
		"max_records":          "1",
		"name":                 volume,
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("fetch volume uuid", err)
	records := ontapclient.Records(volResp)
	if len(records) == 0 {
		log.Fatalf("ABORTED — volume '%s' not found on SVM '%s' after creation", volume, svm)
	}
	uuid := ontapclient.NestedStr(records[0], "uuid")
	log.Printf("volume '%s' | uuid=%s", volume, uuid)
	return uuid
}

// ensureExportPolicy creates an NFS export policy if it does not exist.
// Returns the numeric policy ID, which is required to manage rules under the policy.
func ensureExportPolicy(ctx context.Context, client *ontapclient.Client, svm, policyName string) int64 {
	checkResp, err := client.Get(ctx, pathExportPolicies, map[string]string{
		"fields":               "name,id",
		"max_records":          "1",
		"name":                 policyName,
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("check export policy", err)

	if ontapclient.NumRecords(checkResp) == 0 {
		log.Printf("Creating export policy '%s' on SVM '%s'…", policyName, svm)
		_, err := client.Post(ctx, pathExportPolicies, nil, map[string]interface{}{
			"name": policyName,
			"svm":  map[string]string{"name": svm},
		})
		dieOnErr("create export policy", err)
		log.Printf("Export policy '%s' created successfully", policyName)
	} else {
		log.Printf("Export policy '%s' already exists — skipping create", policyName)
	}

	// Always fetch the policy ID regardless of whether it was just created or pre-existed.
	policyResp, err := client.Get(ctx, pathExportPolicies, map[string]string{
		"fields":               "name,id",
		"max_records":          "1",
		"name":                 policyName,
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("fetch export policy id", err)
	pRecords := ontapclient.Records(policyResp)
	if len(pRecords) == 0 {
		log.Fatalf("ABORTED — export policy '%s' not found on SVM '%s' after creation", policyName, svm)
	}
	policyID := int64(ontapclient.NestedFloat(pRecords[0], "id"))
	log.Printf("export policy '%s' | id=%d", policyName, policyID)
	return policyID
}

// ensureClientRule adds a client-match rule to the given export policy.
// Skips creation if a rule with an identical client-match entry already exists.
func ensureClientRule(ctx context.Context, client *ontapclient.Client, policyID int64, clientMatch string) {
	rulesPath := fmt.Sprintf("%s/%d/rules", pathExportPolicies, policyID)
	rulesResp, err := client.Get(ctx, rulesPath, map[string]string{
		"fields": "index,clients",
	})
	dieOnErr("list export policy rules", err)

	for _, rule := range ontapclient.Records(rulesResp) {
		clients, _ := rule["clients"].([]interface{})
		for _, c := range clients {
			cm, _ := c.(map[string]interface{})
			if match, _ := cm["match"].(string); match == clientMatch {
				log.Printf("Client rule '%s' already exists in policy — skipping", clientMatch)
				return
			}
		}
	}

	log.Printf("Adding client rule '%s' to policy id=%d…", clientMatch, policyID)
	_, err = client.Post(ctx, rulesPath, nil, map[string]interface{}{
		"clients":   []map[string]string{{"match": clientMatch}},
		"ro_rule":   []string{"any"},
		"rw_rule":   []string{"any"},
		"superuser": []string{"any"},
	})
	dieOnErr("add client rule", err)
	log.Printf("Client rule '%s' added successfully", clientMatch)
}

// assignPolicy PATCHes the volume to assign the named export policy.
// Polls the async job when ONTAP returns one rather than an immediate 200 OK.
func assignPolicy(ctx context.Context, client *ontapclient.Client, volumeUUID, policyName string) {
	patchResp, err := client.Patch(ctx,
		fmt.Sprintf("%s/%s", ontapclient.PathStorageVolumes, volumeUUID),
		nil,
		map[string]interface{}{
			"nas": map[string]interface{}{
				"export_policy": map[string]string{"name": policyName},
			},
		},
	)
	dieOnErr("assign export policy", err)

	if jobUUID := ontapclient.NestedStr(patchResp, "job", "uuid"); jobUUID != "" {
		log.Printf("  assign policy job: %s", jobUUID)
		if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Fatalf("assign policy job failed: %v", err)
		}
	}
	log.Printf("Export policy '%s' assigned to volume uuid=%s", policyName, volumeUUID)
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }