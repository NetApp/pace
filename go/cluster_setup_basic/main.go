// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

// Cluster Setup — create a storage cluster from two pre-cluster nodes (ONTAP 9 unified).
//
// Steps:
//
//	1  discoverNodes   — GET /cluster/nodes (membership=available, retry 3x/30s)
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
	"fmt"
	"log"
	"os"
	"strings"
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

	host := mustEnv("ONTAP_HOST")
	user := envOrDefault("ONTAP_USER", "admin")
	pass := envOrDefault("ONTAP_PASS", "") // empty on pre-cluster nodes

	log.Printf("Cluster setup starting — connecting to %s", host)

	client := ontapclient.New(host, user, pass, false)
	defer client.Close()

	// Step 1: Discover available nodes (retry 3x)
	log.Println("=== Step 1: Discover nodes ===")
	discoverNodes(client, 3, 30)

	// Step 2: Find local node
	log.Println("=== Step 2: Discover local node ===")
	localNode := discoverLocal(client)
	localUUID := ontapclient.NestedStr(localNode, "uuid")

	// Step 3: Find partner node
	log.Println("=== Step 3: Discover partner node ===")
	partnerNode := discoverPartner(client, localUUID)

	// Step 4: Create cluster
	log.Println("=== Step 4: Create cluster ===")
	jobUUID := createCluster(client, localNode, partnerNode)

	// Step 5: Track job — switch to cluster credentials first
	log.Println("=== Step 5: Track cluster creation job ===")
	clusterPass := mustEnv("CLUSTER_PASS")
	clusterMgmtIP := mustEnv("CLUSTER_MGMT_IP")
	trackJob(host, user, clusterPass, jobUUID)

	log.Printf("=== CLUSTER CREATED ===\n"+
		"  Name    : %s\n"+
		"  UI      : https://%s\n"+
		"  Login   : %s / %s",
		mustEnv("CLUSTER_NAME"), clusterMgmtIP, user, clusterPass)
}

// discoverNodes GETs /cluster/nodes with membership=available, retrying up to maxAttempts times.
func discoverNodes(client *ontapclient.Client, maxAttempts, delaySecs int) {
	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		resp, err := client.Get(clusterNodesPath, map[string]string{
			"fields":     nodeFields,
			"membership": "available",
		})
		if err == nil {
			log.Printf("discover_nodes — %d node(s) found", ontapclient.NumRecords(resp))
			return
		}
		lastErr = err
		if attempt < maxAttempts {
			log.Printf("discover_nodes failed (attempt %d/%d), retrying in %ds — %v",
				attempt, maxAttempts, delaySecs, err)
			time.Sleep(time.Duration(delaySecs) * time.Second)
		}
	}
	log.Fatalf("discover_nodes failed after %d attempts: %v", maxAttempts, lastErr)
}

// discoverLocal finds the local node (the one with management_interfaces set).
// Returns the first matching node record.
func discoverLocal(client *ontapclient.Client) map[string]interface{} {
	resp, err := client.Get(clusterNodesPath, map[string]string{
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
func discoverPartner(client *ontapclient.Client, localUUID string) map[string]interface{} {
	resp, err := client.Get(clusterNodesPath, map[string]string{
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
func createCluster(client *ontapclient.Client, localNode, partnerNode map[string]interface{}) string {
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
		"name_servers":         map[string]interface{}{},
		"ntp_servers":          map[string]interface{}{},
		"dns_domains":          map[string]interface{}{},
		"configuration_backup": map[string]interface{}{},
	}

	resp, err := client.Post("/cluster?keep_precluster_config=true", body)
	dieOnErr("create_cluster", err)

	jobUUID := ontapclient.JobUUID(resp)
	log.Printf("create_cluster — job %s", jobUUID)
	return jobUUID
}

// trackJob switches to cluster credentials then polls the job until complete.
// After POST /cluster the node switches to full cluster mode and requires CLUSTER_PASS.
func trackJob(host, user, clusterPass, jobUUID string) {
	clusterClient := ontapclient.New(host, user, clusterPass, false)
	defer clusterClient.Close()

	if _, err := clusterClient.PollJob(jobUUID, 10); err != nil {
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
