---
applyTo: "**/ontap/**"
---
<!-- Generated from ai/ontap/conventions.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# ONTAP conventions

These rules apply to every example under an `ontap/` product directory.

## ONTAP API rules

- Use ONLY ONTAP REST APIs - no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ REST endpoints.
- See [docs/ontap-api-patterns.md](../../../docs/ontap-api-patterns.md) for endpoints,
  auth, and async job handling.

## Python conventions

- Import and use [python/ontap/ontap_client.py](../../../python/ontap/ontap_client.py) - never build a new HTTP client.
- Authenticate via `OntapClient.from_env()` (reads `ONTAP_HOST`, `ONTAP_USER` (default `admin`), `ONTAP_PASS`, `ONTAP_VERIFY_SSL` (default `false`)).
- Operational params via `argparse` with env-var fallbacks.
- Async jobs: `job_uuid = resp["job"]["uuid"]; client.poll_job(job_uuid)`.
- Logging via `logging` module - never `print()`.

## Ansible conventions

- Playbooks use `netapp.ontap` FQCNs with `use_rest: always`.
- Every ONTAP task: `use_rest: always`, `no_log: false`, all five connection params.
- `hosts: ontap`, `gather_facts: false`, `connection: local`.
- Collection pin: `netapp.ontap >= 22.12.0`.

## Terraform conventions

- Modules use the `NetApp/netapp-ontap` provider `~> 2.5`.
- `required_version >= 1.4`, provider `~> 2.5`.
- `connection_profiles` with `cx_profile_name = "cluster1"`.
- `sensitive = true` on password variables.
- Four files per module: `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`.

## Go conventions

- Import and use [go/ontap/ontapclient/ontap_client.go](../../../go/ontap/ontapclient/ontap_client.go) — never build a new HTTP client.
- Authenticate via `ontapclient.FromEnv()` (reads `ONTAP_HOST`, `ONTAP_PASS`) or
  `ontapclient.New(host, user, pass, false)` for multi-cluster scenarios.
- Each program lives in its own subdirectory under `go/<product>/` with a single `main.go`.
- All env vars: required via `mustEnv()`, optional via `envOrDefault()`.
- Load `.env` file with `loadDotEnv()` at the start of `main()`.
- Async jobs: `client.PollJob(ctx, uuid)`.
- Logging: `log.Printf(...)` — never `fmt.Print()`.
- Pass `context.Background()` through all API calls.
- Module path: `github.com/netapp/pace/go` — one module for every product; do not
  create new `go.mod` files. Packages nest under it, e.g.
  `github.com/netapp/pace/go/ontap/ontapclient`.
