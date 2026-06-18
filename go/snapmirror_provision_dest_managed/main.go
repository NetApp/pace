// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// SnapMirror Provision — Destination-Managed view.
//
// All SnapMirror API calls driven from the DESTINATION cluster.
// Source RW volume must already exist; dest DP volume is auto-created.
//
// Steps:
//  1. Verify source cluster connectivity
//  2. Verify dest cluster connectivity
//  3. Setup cluster peer (auto-create if missing)
//  4. Validate source volume exists and is RW
//  5. Get dest aggregate
//  6. Setup SVM peer (auto-create if missing)
//  7. Auto-create dest DP volume (skip if already exists)
//  8. Validate dest DP volume exists
//  9. Check if relationship already exists
//  10. Create + initialize SnapMirror relationship
//  11. Poll create/init job
//  12. Fetch relationship UUID
//  13. Initialize relationship (trigger baseline transfer)
//  14. Wait for state = snapmirrored
//  15. Validate health + print final report
//
// Prerequisites:
//  1. ONTAP 9.8+ on both clusters
//  2. SnapMirror licence installed on both clusters
//  3. At least one intercluster LIF on each cluster
//  4. Admin credentials for both clusters
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
	"strings"
	"time"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

const (
	pathClusterPeers = "/cluster/peers"
	pathSVMPeers     = "/svm/peers"
	peerFields       = "name,uuid,status.state"
)

// smRelConfig groups SnapMirror relationship parameters to keep function signatures compact.
type smRelConfig struct {
	destSVM, destVolume, sourceSVMAlias, sourceVolume, peerName, smPolicy string
}

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

	// === Phase A: Source pre-flight ===
	log.Println("=== Phase A: Source pre-flight ===")
	srcVol := phaseASourcePreflight(ctx, src, sourceSVM, sourceVolume, sourceHost)
	srcVolSize := int64(ontapclient.NestedFloat(srcVol, "space", "size"))

	// === Phase B: Dest pre-flight ===
	log.Println("=== Phase B: Dest pre-flight ===")
	dstCluster, err := dst.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get dest cluster", err)
	log.Printf("DEST CLUSTER   | name=%s | ontap=%s",
		ontapclient.NestedStr(dstCluster, "name"),
		ontapclient.NestedStr(dstCluster, "version", "full"))

	// === Phase B0: Cluster peer setup ===
	log.Println("=== Phase B0: Cluster peer setup ===")
	srcPeerName, peerName, dstPeerUUID := setupClusterPeer(ctx, src, dst, sourceSVM, destSVM)

	aggrResp, err := dst.Get(ctx, "/storage/aggregates", map[string]string{
		"fields":      "name,state,space.block_storage.available",
		"state":       "online",
		"max_records": "1",
		"order_by":    "space.block_storage.available desc",
	})
	dieOnErr("get dest aggregate", err)
	aggrName := ""
	aggrs := ontapclient.Records(aggrResp)
	if len(aggrs) > 0 {
		aggrName = ontapclient.NestedStr(aggrs[0], "name")
	}
	if aggrName == "" {
		log.Fatal("ABORTED — no aggregates found on destination cluster")
	}
	log.Printf("DEST AGGREGATE | name=%s", aggrName)

	// === Phase B1: SVM peer setup ===
	log.Println("=== Phase B1: SVM peer setup ===")
	sourceSVMAlias := setupSVMPeer(ctx, src, dst, sourceSVM, destSVM, srcPeerName, peerName, dstPeerUUID)

	// === Phase C: Dest volume setup ===
	log.Println("=== Phase C: Dest volume setup ===")
	_, err = dst.Post(ctx, "/storage/volumes", map[string]string{"return_timeout": "120"}, map[string]interface{}{
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
	} else {
		log.Printf("DEST VOLUME    | created '%s' on aggregate '%s'", destVolume, aggrName)
	}

	dstVolResp, err := dst.Get(ctx, "/storage/volumes", map[string]string{
		"fields":               "name,uuid,state,type",
		"max_records":          "1",
		"name":                 destVolume,
		ontapclient.KeySVMName: destSVM,
	})
	dieOnErr("verify dest volume", err)
	dstVols := ontapclient.Records(dstVolResp)
	if len(dstVols) == 0 {
		log.Fatalf("ABORTED — dest volume '%s' not found on SVM '%s' after create", destVolume, destSVM)
	}
	dstVol := dstVols[0]
	log.Printf("DEST VOLUME    | svm=%s | name=%s | uuid=%s | state=%s | type=%s",
		destSVM,
		ontapclient.NestedStr(dstVol, "name"),
		ontapclient.NestedStr(dstVol, "uuid"),
		ontapclient.NestedStr(dstVol, "state"),
		ontapclient.NestedStr(dstVol, "type"))

	// === Phase D: Relationship setup ===
	log.Println("=== Phase D: Relationship setup ===")
	relUUID := phaseDSetupRelationship(ctx, src, dst, smRelConfig{
		destSVM: destSVM, destVolume: destVolume,
		sourceSVMAlias: sourceSVMAlias, sourceVolume: sourceVolume,
		peerName: peerName, smPolicy: smPolicy,
	})

	// === Phase E: Convergence polling ===
	log.Println("=== Phase E: Convergence polling ===")
	if _, err := dst.WaitSnapmirrored(ctx, relUUID, 15*time.Second, 30*time.Minute); err != nil {
		log.Fatalf("wait snapmirrored: %v", err)
	}

	// === Phase F: Final validation ===
	log.Println("=== Phase F: Final validation ===")
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

// phaseASourcePreflight verifies source cluster connectivity and validates the source volume.
func phaseASourcePreflight(ctx context.Context, src *ontapclient.Client, sourceSVM, sourceVolume, sourceHost string) map[string]interface{} {
	srcCluster, err := src.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	dieOnErr("get source cluster", err)
	log.Printf("SOURCE CLUSTER | name=%s | ontap=%s",
		ontapclient.NestedStr(srcCluster, "name"),
		ontapclient.NestedStr(srcCluster, "version", "full"))

	srcVolResp, err := src.Get(ctx, "/storage/volumes", map[string]string{
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
	log.Printf("SOURCE VOLUME  | svm=%s | name=%s | uuid=%s | state=%s | type=%s | size=%.0f",
		sourceSVM,
		ontapclient.NestedStr(srcVol, "name"),
		ontapclient.NestedStr(srcVol, "uuid"),
		ontapclient.NestedStr(srcVol, "state"),
		ontapclient.NestedStr(srcVol, "type"),
		ontapclient.NestedFloat(srcVol, "space", "size"))
	return srcVol
}

// getICLIFIPs returns intercluster LIF IP addresses from a cluster.
func getICLIFIPs(ctx context.Context, client *ontapclient.Client) []string {
	resp, err := client.Get(ctx, "/network/ip/interfaces", map[string]string{
		"fields":      "name,ip.address,services",
		"max_records": "50",
	})
	if err != nil {
		return nil
	}
	var ips []string
	for _, r := range ontapclient.Records(resp) {
		services, _ := r["services"].([]interface{})
		for _, s := range services {
			if strings.Contains(fmt.Sprintf("%v", s), "intercluster") {
				if ip := ontapclient.NestedStr(r, "ip", "address"); ip != "" {
					ips = append(ips, ip)
					break
				}
			}
		}
	}
	return ips
}

// checkICLIFPreconditions validates intercluster LIFs exist on both clusters.
func checkICLIFPreconditions(srcIPs, dstIPs []string) {
	if len(srcIPs) == 0 {
		log.Fatal("PRE-CONDITION FAILED | Source cluster has no intercluster LIFs.\n" +
			"  SnapMirror requires at least one IC LIF on each cluster.")
	}
	if len(dstIPs) == 0 {
		log.Fatal("PRE-CONDITION FAILED | Dest cluster has no intercluster LIFs.\n" +
			"  SnapMirror requires at least one IC LIF on each cluster.")
	}
	subnet24 := func(ip string) string {
		parts := strings.SplitN(ip, ".", 4)
		if len(parts) >= 3 {
			return parts[0] + "." + parts[1] + "." + parts[2]
		}
		return ip
	}
	srcSubnets := map[string]bool{}
	for _, ip := range srcIPs {
		srcSubnets[subnet24(ip)] = true
	}
	dstSubnets := map[string]bool{}
	for _, ip := range dstIPs {
		dstSubnets[subnet24(ip)] = true
	}
	shared := false
	for s := range srcSubnets {
		if dstSubnets[s] {
			shared = true
			break
		}
	}
	if !shared {
		log.Printf("PRE-CONDITION WARNING | IC LIFs are on different subnets.\n"+
			"  src IPs : %v\n  dst IPs : %v\n"+
			"  SnapMirror data transfers require TCP 11104 and 11105 to be open between these subnets.",
			srcIPs, dstIPs)
	} else {
		log.Printf("PRE-CONDITION OK   | IC LIFs share a common subnet — transfers should work")
	}
}

// setupClusterPeer ensures a cluster peer exists; auto-creates if missing.
// Returns (srcPeerName, dstPeerName, dstPeerUUID).
func setupClusterPeer(ctx context.Context, src, dst *ontapclient.Client, sourceSVM, destSVM string) (string, string, string) {
	okStates := map[string]bool{"available": true, "partial": true, "pending": true}

	dstCP, err := dst.Get(ctx, pathClusterPeers, map[string]string{
		"fields":      peerFields,
		"max_records": "10",
	})
	dieOnErr("get dest cluster peers", err)

	for _, p := range ontapclient.Records(dstCP) {
		state := ontapclient.NestedStr(p, "status", "state")
		if !okStates[state] {
			continue
		}
		// Peer already exists
		srcCP, err2 := src.Get(ctx, pathClusterPeers, map[string]string{
			"fields":      peerFields,
			"max_records": "10",
		})
		if err2 != nil {
			log.Printf("get src cluster peers: %v", err2)
		}
		srcPeerName := ""
		for _, q := range ontapclient.Records(srcCP) {
			if okStates[ontapclient.NestedStr(q, "status", "state")] {
				srcPeerName = ontapclient.NestedStr(q, "name")
				break
			}
		}
		srcIPs := getICLIFIPs(ctx, src)
		dstIPs := getICLIFIPs(ctx, dst)
		log.Printf("CLUSTER PEER   | already peered — dst sees src as '%s' (state=%s) — skipping",
			ontapclient.NestedStr(p, "name"), state)
		log.Printf("IC LIFs        | src=%v  dst=%v", srcIPs, dstIPs)
		checkICLIFPreconditions(srcIPs, dstIPs)
		return srcPeerName, ontapclient.NestedStr(p, "name"), ontapclient.NestedStr(p, "uuid")
	}

	// No existing peer — auto-create
	log.Println("CLUSTER PEER   | no existing peer found — auto-creating")
	srcIPs := getICLIFIPs(ctx, src)
	dstIPs := getICLIFIPs(ctx, dst)
	log.Printf("CLUSTER PEER   | src IC LIFs=%v  dst IC LIFs=%v", srcIPs, dstIPs)
	checkICLIFPreconditions(srcIPs, dstIPs)
	return createNewClusterPeer(ctx, src, dst, srcIPs, dstIPs, sourceSVM, destSVM)
}

// createNewClusterPeer posts a new cluster peer on both sides.
// Returns (srcPeerName, dstPeerName, dstPeerUUID).
func createNewClusterPeer(ctx context.Context, src, dst *ontapclient.Client, srcIPs, dstIPs []string, sourceSVM, destSVM string) (string, string, string) {
	if len(srcIPs) == 0 {
		log.Fatal("ABORTED — no intercluster LIFs found on source cluster.")
	}
	if len(dstIPs) == 0 {
		log.Fatal("ABORTED — no intercluster LIFs found on dest cluster.")
	}

	peerAddrs := make([]string, len(dstIPs))
	copy(peerAddrs, dstIPs)
	srcResp, err := src.Post(ctx, pathClusterPeers, nil, map[string]interface{}{
		"peer_addresses":      peerAddrs,
		"generate_passphrase": true,
		"encryption":          map[string]string{"proposed": "tls-psk"},
		"initial_allowed_svms": []map[string]string{
			{"name": sourceSVM},
		},
	})
	dieOnErr("create cluster peer on source", err)
	passphrase, _ := srcResp["passphrase"].(string)
	if passphrase == "" {
		log.Fatal("ABORTED — cluster peer response missing passphrase field")
	}
	log.Println("CLUSTER PEER   | created on source")

	dstPeerAddrs := make([]string, len(srcIPs))
	copy(dstPeerAddrs, srcIPs)
	_, err = dst.Post(ctx, pathClusterPeers, nil, map[string]interface{}{
		"peer_addresses": dstPeerAddrs,
		"passphrase":     passphrase,
		"initial_allowed_svms": []map[string]string{
			{"name": destSVM},
		},
	})
	dieOnErr("accept cluster peer on dest", err)
	log.Println("CLUSTER PEER   | accepted on dest")

	time.Sleep(5 * time.Second)
	return fetchCreatedPeerNames(ctx, src, dst)
}

// fetchCreatedPeerNames retrieves peer names from both clusters after creation.
func fetchCreatedPeerNames(ctx context.Context, src, dst *ontapclient.Client) (string, string, string) {
	okStates := map[string]bool{"available": true, "partial": true, "pending": true}
	dstCP, err := dst.Get(ctx, pathClusterPeers, map[string]string{"fields": peerFields, "max_records": "10"})
	if err != nil {
		log.Fatalf("ABORTED — could not query cluster peers on destination: %v", err)
	}
	dstPeer := map[string]interface{}{}
	for _, p := range ontapclient.Records(dstCP) {
		if okStates[ontapclient.NestedStr(p, "status", "state")] {
			dstPeer = p
			break
		}
	}
	if len(dstPeer) == 0 {
		log.Fatal("ABORTED — no usable cluster peer found on destination after creation")
	}
	srcCP, err := src.Get(ctx, pathClusterPeers, map[string]string{"fields": peerFields, "max_records": "10"})
	if err != nil {
		log.Fatalf("ABORTED — could not query cluster peers on source: %v", err)
	}
	srcPeer := map[string]interface{}{}
	for _, p := range ontapclient.Records(srcCP) {
		if okStates[ontapclient.NestedStr(p, "status", "state")] {
			srcPeer = p
			break
		}
	}
	if len(srcPeer) == 0 {
		log.Fatal("ABORTED — no usable cluster peer found on source after creation")
	}
	log.Printf("CLUSTER PEER   | dst sees src as '%s'", ontapclient.NestedStr(dstPeer, "name"))
	return ontapclient.NestedStr(srcPeer, "name"),
		ontapclient.NestedStr(dstPeer, "name"),
		ontapclient.NestedStr(dstPeer, "uuid")
}

// grantSVMPeerPermission grants SnapMirror peer-permission on the source SVM.
func grantSVMPeerPermission(ctx context.Context, src *ontapclient.Client, sourceSVM, srcPeerName string) {
	_, err := src.Post(ctx, "/svm/peer-permissions", nil, map[string]interface{}{
		"svm":          map[string]string{"name": sourceSVM},
		"cluster_peer": map[string]string{"name": srcPeerName},
		"applications": []string{"snapmirror"},
	})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if errors.As(err, &apiErr) && (apiErr.ErrorCode() == "13001" || apiErr.ErrorCode() == "917927") {
			log.Println("SVM PEER       | peer-permission already exists — skipping")
			return
		}
		log.Fatalf("SVM PEER       | peer-permission failed: %v", err)
	}
	log.Println("SVM PEER       | peer-permission granted on source")
}

// createSVMPeerRelationship creates the SVM peer relationship on the destination.
func createSVMPeerRelationship(ctx context.Context, dst *ontapclient.Client, destSVM, sourceSVM, dstPeerName string) {
	resp, err := dst.Post(ctx, pathSVMPeers, nil, map[string]interface{}{
		"svm": map[string]string{"name": destSVM},
		"peer": map[string]interface{}{
			"svm":     map[string]string{"name": sourceSVM},
			"cluster": map[string]string{"name": dstPeerName},
		},
		"applications": []string{"snapmirror"},
	})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if errors.As(err, &apiErr) && (apiErr.ErrorCode() == "13001" || apiErr.ErrorCode() == "917927") {
			log.Println("SVM PEER       | already exists — skipping")
			return
		}
		log.Fatalf("SVM PEER       | create failed: %v", err)
	}
	if jobUUID := ontapclient.JobUUID(resp); jobUUID != "" {
		if _, err := dst.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Printf("poll svm peer job: %v", err)
		}
	}
	log.Printf("SVM PEER       | created '%s' <-> '%s'", destSVM, sourceSVM)
}

// setupSVMPeer ensures SVM peer exists; returns the source SVM alias used in SnapMirror paths.
func setupSVMPeer(ctx context.Context, src, dst *ontapclient.Client, sourceSVM, destSVM, srcPeerName, dstPeerName, srcClusterPeerUUID string) string {
	svmResp, err := dst.Get(ctx, pathSVMPeers, map[string]string{
		"fields":               "uuid,name,state,peer",
		ontapclient.KeySVMName: destSVM,
	})
	dieOnErr("get svm peers", err)

	for _, p := range ontapclient.Records(svmResp) {
		state := ontapclient.NestedStr(p, "state")
		if state != "peered" && state != "initiated" {
			continue
		}
		if ontapclient.NestedStr(p, "peer", "cluster", "uuid") != srcClusterPeerUUID {
			continue
		}
		alias := ontapclient.NestedStr(p, "peer", "svm", "name")
		if alias == "" {
			alias = sourceSVM
		}
		log.Printf("SVM PEER       | already peered '%s' <-> '%s' (alias='%s', state=%s) — skipping",
			destSVM, sourceSVM, alias, state)
		return alias
	}

	grantSVMPeerPermission(ctx, src, sourceSVM, srcPeerName)
	createSVMPeerRelationship(ctx, dst, destSVM, sourceSVM, dstPeerName)

	svmResp2, err := dst.Get(ctx, pathSVMPeers, map[string]string{
		"fields":               "uuid,name,state,peer",
		ontapclient.KeySVMName: destSVM,
	})
	if err != nil {
		return sourceSVM
	}
	for _, p := range ontapclient.Records(svmResp2) {
		if ontapclient.NestedStr(p, "peer", "cluster", "uuid") == srcClusterPeerUUID {
			alias := ontapclient.NestedStr(p, "peer", "svm", "name")
			if alias == "" {
				alias = sourceSVM
			}
			return alias
		}
	}
	return sourceSVM
}

// phaseDSetupRelationship creates and initializes the SnapMirror relationship; returns its UUID.
func phaseDSetupRelationship(ctx context.Context, src, dst *ontapclient.Client, cfg smRelConfig) string {
	existing, err := dst.Get(ctx, "/snapmirror/relationships", map[string]string{
		"fields":           "uuid,state,healthy",
		"destination.path": cfg.destSVM + ":" + cfg.destVolume,
		"max_records":      "1",
	})
	dieOnErr("check existing relationship", err)
	log.Printf("RELATIONSHIP CHECK | existing=%d", ontapclient.NumRecords(existing))

	createResp, err := dst.Post(ctx, "/snapmirror/relationships", map[string]string{"return_timeout": "120"}, map[string]interface{}{
		"source": map[string]interface{}{
			"path":    cfg.sourceSVMAlias + ":" + cfg.sourceVolume,
			"cluster": map[string]string{"name": cfg.peerName},
		},
		"destination": map[string]string{"path": cfg.destSVM + ":" + cfg.destVolume},
		"policy":      map[string]string{"name": cfg.smPolicy},
	})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if errors.As(err, &apiErr) && apiErr.ErrorCode() == "917927" {
			log.Printf("create_and_initialize_relationship — relationship already exists, skipping create")
		} else {
			log.Fatalf("create_and_initialize_relationship: %v", err)
		}
	} else if jobUUID := ontapclient.JobUUID(createResp); jobUUID != "" {
		if _, err := dst.PollJob(ctx, jobUUID, 10*time.Second); err != nil {
			log.Printf("poll create job — %v", err)
		}
	}

	relResp, err := dst.Get(ctx, "/snapmirror/relationships", map[string]string{
		"fields":           "uuid,source.path,destination.path,state,lag_time,healthy,policy.name",
		"destination.path": cfg.destSVM + ":" + cfg.destVolume,
		"max_records":      "1",
	})
	dieOnErr("get relationship", err)
	relRecords := ontapclient.Records(relResp)
	if len(relRecords) == 0 {
		log.Fatalf("ABORTED — SnapMirror relationship not found for '%s:%s'", cfg.destSVM, cfg.destVolume)
	}
	rel := relRecords[0]
	relUUID := ontapclient.NestedStr(rel, "uuid")
	log.Printf("RELATIONSHIP   | uuid=%s | state=%s | healthy=%v | policy=%s",
		relUUID,
		ontapclient.NestedStr(rel, "state"),
		rel["healthy"],
		ontapclient.NestedStr(rel, "policy", "name"))

	_, err = dst.Post(ctx, fmt.Sprintf("/snapmirror/relationships/%s/transfers", relUUID), map[string]string{"return_timeout": "120"}, map[string]interface{}{})
	if err != nil {
		var apiErr *ontapclient.OntapApiError
		if errors.As(err, &apiErr) && apiErr.ErrorCode() == "13303812" {
			srcIPs := getICLIFIPs(ctx, src)
			dstIPs := getICLIFIPs(ctx, dst)
			log.Fatalf("ABORTED — SnapMirror initialize failed: intercluster LIF connectivity issue.\n"+
				"  Error   : %v\n  src IC  : %v\n  dst IC  : %v\n"+
				"  Cause   : TCP ports 11104/11105 are likely blocked between these IPs.",
				err, srcIPs, dstIPs)
		}
		log.Printf("initialize_relationship — %v (may already be initialized)", err)
	}
	return relUUID
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
