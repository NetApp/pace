// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// Cluster Setup — create a storage cluster from two pre-cluster nodes (ONTAP 9 unified).
//
// Steps:
//
//	1  waitForNodes   — GET /cluster/nodes (membership=available, retry 3x/30s)
//	2  discoverLocal   — isolate the local node  (management_interfaces != null)
//	3  discoverPartner — isolate the partner node (exclude local node UUID)
//	4  createCluster   — POST /cluster
//	5  trackJob        — switch to cluster credentials, poll job until complete
//
// Prerequisites:
//  1. Two ONTAP 9 nodes in pre-cluster state (factory default or freshly wiped)
//  2. Both nodes reachable at their management IPs
//  3. Node 1 (ONTAP_HOST) must have at least one cluster interface already configured
//
// Usage:
//
//	export ONTAP_HOST=10.x.x.x        ONTAP_USER=admin  ONTAP_PASS=
//	export CLUSTER_NAME=mycluster     CLUSTER_PASS=secret
//	export CLUSTER_MGMT_IP=10.x.x.x  CLUSTER_NETMASK=255.255.192.0  CLUSTER_GATEWAY=10.x.x.1
//	export PARTNER_MGMT_IP=10.x.x.y
//	go run .
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	ontapclient "github.com/netapp/pace/go/ontapclient"
)

// ---------------------------------------------------------------------------

const nodeFields = "name,uuid,model,state,ha,version,serial_number,membership," +
	"cluster_interfaces,management_interfaces,metrocluster"

const clusterNodesPath = "/cluster/nodes"

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	host := mustEnv("ONTAP_HOST")
	user := envOrDefault("ONTAP_USER", "admin")
	pass := envOrDefault("ONTAP_PASS", "") // empty on pre-cluster nodes

	log.Printf("Cluster setup starting — connecting to %s", host)

	client := ontapclient.New(host, user, pass, false)
	defer client.Close()

	// Step 1: Discover available nodes (retry 3x)
	log.Println("=== Step 1: Discover nodes ===")
	waitForNodes(ctx, client, 3, 30*time.Second)

	// Step 2: Find local node
	log.Println("=== Step 2: Discover local node ===")
	localNode := discoverLocal(ctx, client)
	localUUID := ontapclient.NestedStr(localNode, "uuid")

	// Step 3: Find partner node
	log.Println("=== Step 3: Discover partner node ===")
	partnerNode := discoverPartner(ctx, client, localUUID)

	// Step 4: Create cluster
	log.Println("=== Step 4: Create cluster ===")
	jobUUID := createCluster(ctx, client, localNode, partnerNode)

	// Step 5: Track job — switch to cluster credentials first
	log.Println("=== Step 5: Track cluster creation job ===")
	clusterPass := mustEnv("CLUSTER_PASS")
	clusterMgmtIP := mustEnv("CLUSTER_MGMT_IP")
	trackJob(ctx, host, user, clusterPass, jobUUID)

	log.Printf("=== CLUSTER CREATED ===\n"+
		"  Name    : %s\n"+
		"  UI      : https://%s\n"+
		"  User    : %s",
		mustEnv("CLUSTER_NAME"), clusterMgmtIP, user)
}

// waitForNodes GETs /cluster/nodes with membership=available, retrying up to maxAttempts times.
// Acts as a readiness guard — the caller proceeds only when nodes are reachable.
func waitForNodes(ctx context.Context, client *ontapclient.Client, maxAttempts int, delay time.Duration) {
	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		resp, err := client.Get(ctx, clusterNodesPath, map[string]string{
			"fields":     nodeFields,
			"membership": "available",
		})
		if err == nil {
			log.Printf("wait_for_nodes — %d node(s) found", ontapclient.NumRecords(resp))
			return
		}
		lastErr = err
		if attempt < maxAttempts {
			log.Printf("wait_for_nodes failed (attempt %d/%d), retrying in %s — %v",
				attempt, maxAttempts, delay, err)
			time.Sleep(delay)
		}
	}
	log.Fatalf("wait_for_nodes failed after %d attempts: %v", maxAttempts, lastErr)
}

// discoverLocal finds the local node (the one with management_interfaces set).
// Returns the first matching node record.
func discoverLocal(ctx context.Context, client *ontapclient.Client) map[string]interface{} {
	resp, err := client.Get(ctx, clusterNodesPath, map[string]string{
		"fields":                nodeFields,
		"membership":            "available",
		"management_interfaces": "!null",
	})
	dieOnErr("discover_local", err)
	nodes := ontapclient.Records(resp)
	if len(nodes) == 0 {
		log.Fatal("discover_local: no local node returned")
	}
	log.Printf("discover_local  — %s", ontapclient.NestedStr(nodes[0], "name"))
	return nodes[0]
}

// discoverPartner finds the partner node by excluding the local node UUID.
// Returns the first matching node record.
func discoverPartner(ctx context.Context, client *ontapclient.Client, localUUID string) map[string]interface{} {
	resp, err := client.Get(ctx, clusterNodesPath, map[string]string{
		"fields":     nodeFields,
		"membership": "available",
		"uuid":       "!" + localUUID,
	})
	dieOnErr("discover_partner", err)
	nodes := ontapclient.Records(resp)
	if len(nodes) == 0 {
		log.Fatal("discover_partner: no partner node returned")
	}
	log.Printf("discover_partner — %s", ontapclient.NestedStr(nodes[0], "name"))
	return nodes[0]
}

// createCluster POSTs /cluster to create the cluster; returns the job UUID.
func createCluster(ctx context.Context, client *ontapclient.Client, localNode, partnerNode map[string]interface{}) string {
	clusterName := mustEnv("CLUSTER_NAME")
	clusterPass := mustEnv("CLUSTER_PASS")
	clusterMgmtIP := mustEnv("CLUSTER_MGMT_IP")
	clusterNetmask := mustEnv("CLUSTER_NETMASK")
	clusterGateway := mustEnv("CLUSTER_GATEWAY")
	ontapHost := mustEnv("ONTAP_HOST")
	partnerMgmtIP := mustEnv("PARTNER_MGMT_IP")

	localClusterIP := clusterIfaceIP(localNode)
	partnerClusterIP := clusterIfaceIP(partnerNode)

	if localClusterIP == "" {
		log.Fatal("ABORTED — local node has no cluster interface IP")
	}
	if partnerClusterIP == "" {
		log.Fatal("ABORTED — partner node has no cluster interface IP")
	}

	body := map[string]interface{}{
		"name":     clusterName,
		"password": clusterPass,
		"management_interface": map[string]interface{}{
			"ip": map[string]string{
				"address": clusterMgmtIP,
				"netmask": clusterNetmask,
				"gateway": clusterGateway,
			},
		},
		"nodes": []map[string]interface{}{
			{
				"name": fmt.Sprintf("%s-01", clusterName),
				"management_interface": map[string]interface{}{
					"ip": map[string]string{"address": ontapHost},
				},
				"cluster_interface": map[string]interface{}{
					"ip": map[string]string{"address": localClusterIP},
				},
			},
			{
				"name": fmt.Sprintf("%s-02", clusterName),
				"management_interface": map[string]interface{}{
					"ip": map[string]string{"address": partnerMgmtIP},
				},
				"cluster_interface": map[string]interface{}{
					"ip": map[string]string{"address": partnerClusterIP},
				},
			},
		},
	}

	resp, err := client.Post(ctx, "/cluster", map[string]string{"keep_precluster_config": "true"}, body)
	dieOnErr("create_cluster", err)

	jobUUID := ontapclient.JobUUID(resp)
	log.Printf("create_cluster — job %s", jobUUID)
	return jobUUID
}

// trackJob switches to cluster credentials then polls the job until complete.
// After POST /cluster the node reboots its management stack — network errors
// are expected and retried. HTTP-level errors (4xx/5xx) are fatal.
// Delegates to PollJobTolerant which encapsulates the network-retry logic.
func trackJob(ctx context.Context, host, user, clusterPass, jobUUID string) {
	clusterClient := ontapclient.New(host, user, clusterPass, false)
	defer clusterClient.Close()
	if _, err := clusterClient.PollJobTolerant(ctx, jobUUID, 15*time.Second); err != nil {
		log.Fatalf("track_job: %v", err)
	}
}

// clusterIfaceIP extracts the IP address of the first cluster interface from a node record.
func clusterIfaceIP(node map[string]interface{}) string {
	ifaces, _ := node["cluster_interfaces"].([]interface{})
	if len(ifaces) == 0 {
		return ""
	}
	iface, _ := ifaces[0].(map[string]interface{})
	return ontapclient.NestedStr(iface, "ip", "address")
}

func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
