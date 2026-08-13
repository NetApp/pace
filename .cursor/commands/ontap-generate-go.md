<!-- Generated from ai/ontap/generate-go.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# Generate Go Storage Workflow

You are generating a Go program for the **pace** repository.
The program automates a NetApp ONTAP storage task using exclusively REST APIs.

## Task

{task description}

## Reference Files

Use these repository files as the authoritative source for conventions:

- [go/ontap/ontapclient/ontap_client.go](../../go/ontap/ontapclient/ontap_client.go) - shared REST client (MUST import and use this)
- [go/ontap/snapmirror_provision_src_managed/main.go](../../go/ontap/snapmirror_provision_src_managed/main.go) - reference implementation pattern
- [go/ontap/cluster_setup_basic/main.go](../../go/ontap/cluster_setup_basic/main.go) - simpler reference example
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - API endpoints, auth, async jobs
- [docs/example-template/go/example.go](../../docs/example-template/go/example.go) - skeleton to start from
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - naming, CI, quality bar

## Step 1 - Clarify Inputs

Before writing code, identify what information is missing and ask me.
Common inputs: SVM name, volume name/size, aggregate, protocol details,
cluster hostname, special options (snapshot policy, QoS, junction path).

## Step 2 - API Sequence

List the ONTAP REST API calls in execution order:

| # | Method | Endpoint | Key Body/Query Params | Sync/Async | Why |
|---|--------|----------|-----------------------|------------|-----|

Rules:
- ONTAP REST only - no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ endpoints.
- Full endpoint paths (e.g. `/api/storage/volumes`).
- For async calls, include the poll step: `GET /api/cluster/jobs/{uuid}`.

Wait for my confirmation before generating code.

## Step 3 - Generate Go Program

Directory: `go/<product>/<use_case>/main.go` (snake_case directory name)

### Mandatory conventions

- Package declaration: `package main`
- Copyright header as `//` comment lines at the top.
- Package-level doc comment describing what the program does, phases/steps,
  prerequisites (numbered list), and usage with env vars.
- Import the shared client:
  ```go
  import ontapclient "github.com/netapp/pace/go/ontap/ontapclient"
  ```
- Authenticate via `ontapclient.FromEnv()` (reads `ONTAP_HOST`, `ONTAP_USER` (default `"admin"`), `ONTAP_PASS`)
  or `ontapclient.New(host, user, pass, false)` for multi-cluster cases.
- Required env vars via `mustEnv()` helper, optional via `envOrDefault()`.
- Load `.env` file: call `loadDotEnv()` at the start of `main()`.
- Pass `context.Background()` through all API calls.
- Async job polling: `client.PollJob(ctx, uuid)`.
- Logging: `log.Printf(...)` — never `fmt.Print()`.
- Defer `client.Close()` immediately after creating each client.
- Helper patterns:
  ```go
  host := mustEnv("ONTAP_HOST")
  user := envOrDefault("ONTAP_USER", "admin")

  client := ontapclient.New(host, user, pass, false)
  defer client.Close()

  result, err := client.Get(ctx, "/cluster", map[string]string{"fields": "name,version"})
  if err != nil { log.Fatalf("get cluster: %v", err) }

  name := ontapclient.NestedStr(result, "name")
  ```
- No hardcoded credentials.
- Each logical phase prefixed with a log banner:
  ```go
  log.Println("=== Phase A: Description ===")
  ```

### Helper functions to include

Every program must include these helpers (copy from an existing program):

```go
func mustEnv(key string) string         { return ontapclient.MustEnv(key) }
func envOrDefault(k, def string) string { return ontapclient.EnvOrDefault(k, def) }
func dieOnErr(op string, err error)     { ontapclient.DieOnErr(op, err) }
func loadDotEnv()                       { ontapclient.LoadDotEnv() }
```

Do **not** copy-paste standalone implementations — delegate to the shared
`ontapclient` package so any future fixes to env loading propagate everywhere.

### go.mod

The module path is `github.com/netapp/pace/go` — do **not** create a new
`go.mod`. Add the new directory to the existing module.

## Step 4 - Validate

After the code, provide:
1. Exact shell commands to run the program.
2. Error scenarios and how the program handles each.
3. Teardown / cleanup instructions.

## Copyright header (required)

Every generated source file MUST start with the standard NetApp header using
Go line-comment syntax (`//`). The `insert-license` pre-commit hook will add
it automatically, but include it from the start.

```text
// © 2026 NetApp, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
// See the NOTICE file in the repo root for trademark and attribution details.
```

Do **not** duplicate the full trademark text in source files — it lives in
[NOTICE](../../NOTICE) and the LICENSE appendix.
