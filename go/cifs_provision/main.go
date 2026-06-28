// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// CIFS Provision — create a FlexVol (NTFS security style) and a CIFS share with ACL.
//
// Steps:
//
//	0  preflight        — verify cluster connectivity; log cluster name + ONTAP version
//	1  ensureCIFSServer — confirm CIFS server on SVM; optionally create workgroup server
//	2  ensureVolume     — create NTFS FlexVol if it does not exist; poll creation job
//	3  fetchSVMUUID     — GET SVM UUID (required for share and ACL URL paths)
//	4  ensureCIFSShare  — create CIFS share if it does not exist (404-safe check)
//	5  setShareACL      — PATCH share ACL for the given user and permission
//	6  verifyShare      — GET share and log every ACL entry for confirmation
//	7  summary          — log share name, volume, mount path, and ACL
//
// The script is idempotent: re-running with the same parameters skips any step
// that is already complete.
//
// Prerequisites:
//  1. Go 1.22+ installed; run `cd go && go mod download` once to cache deps
//  2. ONTAP 9.8+ cluster with CIFS licence on the target SVM
//  3. Target SVM (SVM_NAME) already exists with a CIFS server configured,
//     or set CREATE_CIFS_SERVER=true to auto-create a workgroup server
//  4. Target aggregate (AGGR_NAME) already online
//
// Usage:
//
//	export ONTAP_HOST=10.x.x.x   ONTAP_USER=admin   ONTAP_PASS=secret
//	export SVM_NAME=vs1
//	export VOLUME_NAME=vol_002
//	export VOLUME_SIZE=100MB
//	export AGGR_NAME=aggr1
//	export SHARE_NAME=cifs_share_demo
//	export ACL_USER=Everyone
//	export ACL_PERMISSION=full_control
//	go run .
//
//	# To auto-create a workgroup CIFS server if none exists on the SVM:
//	export CREATE_CIFS_SERVER=true  CIFS_SERVER_NAME=ONTAP-CIFS  CIFS_WORKGROUP=WORKGROUP
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

const (
	pathCIFSServices = "/protocols/cifs/services"
	pathCIFSShares   = "/protocols/cifs/shares"
	pathSVMs         = "/svm/svms"
)

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	svmName := mustEnv("SVM_NAME")
	volumeName := mustEnv("VOLUME_NAME")
	volumeSize := envOrDefault("VOLUME_SIZE", "100MB")
	aggrName := mustEnv("AGGR_NAME")
	shareName := envOrDefault("SHARE_NAME", "cifs_share_demo")
	shareComment := envOrDefault("SHARE_COMMENT", "Provisioned by pace example")
	aclUser := envOrDefault("ACL_USER", "Everyone")
	aclPermission := envOrDefault("ACL_PERMISSION", "full_control")
	createCIFSServer := envOrDefault("CREATE_CIFS_SERVER", "false") == "true"
	cifsServerName := envOrDefault("CIFS_SERVER_NAME", "ONTAP-CIFS")
	cifsWorkgroup := envOrDefault("CIFS_WORKGROUP", "WORKGROUP")

	client, err := ontapclient.FromEnv()
	dieOnErr("init client", err)
	defer client.Close()

	log.Printf("CIFS provision starting — SVM=%s | volume=%s | share=%s",
		svmName, volumeName, shareName)

	log.Println("=== Step 0: Verify cluster connectivity ===")
	cluster, err := client.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get cluster", err)
	log.Printf("CLUSTER | name=%s | ontap=%s",
		ontapclient.NestedStr(cluster, "name"),
		ontapclient.NestedStr(cluster, "version", "full"))

	log.Println("=== Step 1: Ensure CIFS server ===")
	ensureCIFSServer(ctx, client, svmName, createCIFSServer, cifsServerName, cifsWorkgroup)

	log.Println("=== Step 2: Ensure volume ===")
	ensureVolumeNTFS(ctx, client, svmName, volumeName, volumeSize, aggrName)

	log.Println("=== Step 3: Fetch SVM UUID ===")
	svmUUID := fetchSVMUUID(ctx, client, svmName)

	log.Println("=== Step 4: Ensure CIFS share ===")
	ensureCIFSShare(ctx, client, svmUUID, shareName, volumeName, svmName, shareComment)

	log.Println("=== Step 5: Set share ACL ===")
	setShareACL(ctx, client, svmUUID, shareName, aclUser, aclPermission)

	log.Println("=== Step 6: Verify share ===")
	verifyShare(ctx, client, svmUUID, shareName)

	log.Printf("=== CIFS SHARE PROVISIONED ===\n"+
		"  SVM        : %s\n"+
		"  Volume     : %s\n"+
		"  Share      : %s\n"+
		"  Mount path : /%s\n"+
		"  ACL        : %s → %s",
		svmName, volumeName, shareName, volumeName, aclUser, aclPermission)
}

// ensureCIFSServer verifies a CIFS server exists on the SVM.
// If createServer is true and none is found, creates a workgroup CIFS server.
func ensureCIFSServer(ctx context.Context, client *ontapclient.Client,
	svm string, createServer bool, serverName, workgroup string) {

	resp, err := client.Get(ctx, pathCIFSServices, map[string]string{
		"fields":               "svm.name,enabled",
		"max_records":          "1",
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("check cifs server", err)

	if ontapclient.NumRecords(resp) > 0 {
		log.Printf("CIFS server confirmed on SVM '%s'", svm)
		return
	}

	if !createServer {
		log.Fatalf("ABORTED — no CIFS server on SVM '%s'; set CREATE_CIFS_SERVER=true to auto-create one", svm)
	}

	log.Printf("Creating workgroup CIFS server '%s' in workgroup '%s' on SVM '%s'…",
		serverName, workgroup, svm)
	createResp, err := client.Post(ctx, pathCIFSServices, nil, map[string]interface{}{
		"svm":       map[string]string{"name": svm},
		"name":      serverName,
		"workgroup": workgroup,
		"enabled":   true,
	})
	dieOnErr("create cifs server", err)

	if jobUUID := ontapclient.NestedStr(createResp, "job", "uuid"); jobUUID != "" {
		log.Printf("  CIFS server creation job: %s", jobUUID)
		if _, err := client.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Fatalf("CIFS server creation job failed: %v", err)
		}
	}
	log.Printf("CIFS server '%s' created on SVM '%s'", serverName, svm)
}

// ensureVolumeNTFS creates a FlexVol with NTFS security style if it does not exist.
// The volume is mounted at /<volume> to make it immediately accessible to CIFS clients.
func ensureVolumeNTFS(ctx context.Context, client *ontapclient.Client, svm, volume, size, aggr string) {
	checkResp, err := client.Get(ctx, ontapclient.PathStorageVolumes, map[string]string{
		"fields":               "name,uuid",
		"max_records":          "1",
		"name":                 volume,
		ontapclient.KeySVMName: svm,
	})
	dieOnErr("check volume", err)

	if ontapclient.NumRecords(checkResp) > 0 {
		log.Printf("Volume '%s' already exists — skipping create", volume)
		return
	}

	log.Printf("Creating NTFS volume '%s' (%s) on SVM '%s' aggregate '%s'…", volume, size, svm, aggr)
	createResp, err := client.Post(ctx, ontapclient.PathStorageVolumes, nil, map[string]interface{}{
		"name": volume,
		"svm":  map[string]string{"name": svm},
		"aggregates": []map[string]string{
			{"name": aggr},
		},
		"size": size,
		"nas": map[string]string{
			"security_style": "ntfs",
			"path":           fmt.Sprintf("/%s", volume),
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
}

// fetchSVMUUID returns the UUID for the named SVM.
// The SVM UUID is required to construct the CIFS share and ACL REST URL paths.
func fetchSVMUUID(ctx context.Context, client *ontapclient.Client, svm string) string {
	resp, err := client.Get(ctx, pathSVMs, map[string]string{
		"fields":      "name,uuid",
		"max_records": "1",
		"name":        svm,
	})
	dieOnErr("fetch svm uuid", err)
	records := ontapclient.Records(resp)
	if len(records) == 0 {
		log.Fatalf("ABORTED — SVM '%s' not found", svm)
	}
	uuid := ontapclient.NestedStr(records[0], "uuid")
	log.Printf("SVM '%s' | uuid=%s", svm, uuid)
	return uuid
}

// ensureCIFSShare creates the CIFS share if it does not already exist.
// A GET to the specific share URL is used for the existence check; a 404 response
// means the share is absent and creation proceeds normally.
func ensureCIFSShare(ctx context.Context, client *ontapclient.Client,
	svmUUID, shareName, volume, svm, comment string) {

	sharePath := fmt.Sprintf("%s/%s/%s", pathCIFSShares, svmUUID, shareName)
	_, err := client.Get(ctx, sharePath, map[string]string{"fields": "name"})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if !errors.As(err, &apiErr) || apiErr.StatusCode != 404 {
			dieOnErr("check cifs share", err)
		}
		// 404 — share does not exist; proceed to create.
		log.Printf("Creating CIFS share '%s' on path '/%s'…", shareName, volume)
		_, err = client.Post(ctx, pathCIFSShares, nil, map[string]interface{}{
			"name":    shareName,
			"path":    fmt.Sprintf("/%s", volume),
			"svm":     map[string]string{"name": svm},
			"comment": comment,
		})
		dieOnErr("create cifs share", err)
		log.Printf("CIFS share '%s' created successfully", shareName)
		return
	}
	log.Printf("CIFS share '%s' already exists — skipping create", shareName)
}

// setShareACL PATCHes the share ACL entry for the given user with the specified permission.
func setShareACL(ctx context.Context, client *ontapclient.Client,
	svmUUID, shareName, user, permission string) {

	aclPath := fmt.Sprintf("%s/%s/%s/acls/%s/windows", pathCIFSShares, svmUUID, shareName, user)
	log.Printf("Setting ACL: %s → %s on share '%s'…", user, permission, shareName)
	_, err := client.Patch(ctx, aclPath, nil, map[string]interface{}{
		"permission": permission,
	})
	dieOnErr("set share acl", err)
	log.Printf("ACL set: %s → %s", user, permission)
}

// verifyShare GETs the share and logs every ACL entry for operator confirmation.
func verifyShare(ctx context.Context, client *ontapclient.Client, svmUUID, shareName string) {
	sharePath := fmt.Sprintf("%s/%s/%s", pathCIFSShares, svmUUID, shareName)
	resp, err := client.Get(ctx, sharePath, map[string]string{"fields": "name,path,acls"})
	dieOnErr("verify share", err)

	log.Printf("SHARE | name=%s | path=%s",
		ontapclient.NestedStr(resp, "name"),
		ontapclient.NestedStr(resp, "path"))

	acls, _ := resp["acls"].([]interface{})
	for _, a := range acls {
		acl, _ := a.(map[string]interface{})
		log.Printf("  ACL | user=%s | type=%s | permission=%s",
			ontapclient.NestedStr(acl, "user_or_group"),
			ontapclient.NestedStr(acl, "type"),
			ontapclient.NestedStr(acl, "permission"))
	}
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
