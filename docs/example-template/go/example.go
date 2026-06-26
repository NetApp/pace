// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.

//go:build ignore

// <Use Case Name> — brief description of what this program does.
//
// Steps:
//
//	1  <step one description>
//	2  <step two description>
//
// Prerequisites:
//  1. ONTAP 9.8+ with appropriate licenses
//  2. Network access to the cluster management LIF
//  3. Admin credentials (ONTAP_HOST, ONTAP_PASS)
//
// Usage:
//
//	export ONTAP_HOST=10.x.x.x  ONTAP_USER=admin  ONTAP_PASS=secret
//	go run .
package main

import (
	"context"
	"log"
	"os"
	"strings"

	// When you copy this template into go/<use_case>/main.go the import below
	// resolves automatically — this file lives outside the module root so the
	// path is shown as a comment only.
	// ontapclient "github.com/netapp/pace/go/ontapclient"
)

func main() {
	log.SetFlags(log.LstdFlags)
	loadDotEnv()
	ctx := context.Background()

	host := mustEnv("ONTAP_HOST")
	user := envOrDefault("ONTAP_USER", "admin")
	pass := mustEnv("ONTAP_PASS")

	// Uncomment after copying into go/<use_case>/main.go:
	// client := ontapclient.New(host, user, pass, false)
	// defer client.Close()

	// Step 1: Retrieve or create resources
	log.Println("=== Step 1: Get cluster info ===")
	// cluster, err := client.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
	// if err != nil { log.Fatalf("get cluster: %v", err) }
	// log.Printf("Cluster: %s — %s",
	// 	ontapclient.NestedStr(cluster, "name"),
	// 	ontapclient.NestedStr(cluster, "version", "full"))

	// Step 2: Add your logic here
	_ = ctx
	log.Printf("connecting to %s as %s — add your logic here", host, user)
	_ = pass
}

// ---------------------------------------------------------------------------
// Helpers — copy verbatim into every new Go program in this repo.
// ---------------------------------------------------------------------------

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		log.Fatalf("required env var %s is not set", key)
	}
	return v
}

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// loadDotEnv reads a .env file from the current directory and sets any
// variables that are not already set in the process environment.
func loadDotEnv() {
	data, err := os.ReadFile(".env")
	if err != nil {
		return // no .env file — silently skip
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			os.Setenv(strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1]))
		}
	}
}
