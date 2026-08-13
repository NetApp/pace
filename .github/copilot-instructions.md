# Copilot Instructions for Pace

## Project overview

This repository contains NetApp storage automation examples in Python, Ansible,
and Terraform. Each approach implements the same use cases so users can compare
side-by-side and pick the tool their team already knows.

## Repository layout

Examples are grouped first by tool, then by the NetApp product they target:

```
python/<product>/       # Python script examples (snake_case files)
ansible/<product>/      # Ansible playbook examples (snake_case files)
terraform/<product>/    # Terraform module examples (kebab-case dirs)
go/<product>/           # Go program examples (snake_case subdirs, one main.go each)
docs/                   # Guides, API patterns, comparison docs
.github/prompts/        # Reusable Copilot prompts for workflow generation
```

Products: `ontap` holds every example today. `console` (NetApp Console) adds a
deployment level — `<tool>/console/local/` — and is currently an empty
placeholder. Put new work under the product it targets; never at the tool root.

## Reusable Prompts

This repository ships reusable prompt files in `.github/prompts/`. Use them
from Copilot Chat to generate new workflows that already follow every
convention:

| Prompt | What it does |
|--------|-------------|
| `generate-python` | Generate a Python script using `ontap_client.OntapClient` |
| `generate-ansible` | Generate an Ansible playbook using `netapp.ontap` modules |
| `generate-terraform` | Generate a Terraform module using `NetApp/netapp-ontap` provider |
| `generate-go` | Generate a Go program using `ontapclient.Client` |
| `generate-workflow` | Generate all four implementations at once |
| `plan-api-sequence` | Design the REST API call sequence before writing code |
| `review-contribution` | Review code against CI, naming, and PR requirements |

## Coding conventions

- Python >= 3.11; use modern syntax (PEP 604 unions, f-strings, `match` where appropriate).
- Linter: `ruff` (line length 99, target py311). Run `ruff check python/`.
- All new Python code should have type hints.
- Never hardcode credentials - use env vars, Ansible Vault, or Terraform `sensitive`.
- Ansible playbooks use `netapp.ontap` FQCNs with `use_rest: always`.
- Terraform modules use the `NetApp/netapp-ontap` provider `~> 2.5`.
- Go programs use Go 1.22+; import `go/ontap/ontapclient` — never build a new HTTP client.
- Every generated source file (`.py`, `.yml`, `.tf`, `.sh`, `.html`, `.go`) MUST start
  with the standard NetApp copyright header (see below).

## Copyright header (required on all source files)

Use the comment syntax of the file. Year is `2026`. Full trademark text
lives in `NOTICE`; do not duplicate it in source files.

```text
© 2026 NetApp, Inc. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
See the NOTICE file in the repo root for trademark and attribution details.
```

The `insert-license` pre-commit hook adds and verifies it automatically.
Exempt files: Markdown, `requirements.*`, `ansible/*/inventory/*`,
`ansible/*/group_vars/*`, `*.example`, `dependabot.yml`.

## ONTAP API rules

- Use ONLY ONTAP REST APIs - no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ REST endpoints.
- See `docs/ontap-api-patterns.md` for endpoints, auth, async job handling.

## Python conventions

- Import and use `python/ontap/ontap_client.py` - never build a new HTTP client.
- Authenticate via `OntapClient.from_env()` (reads `ONTAP_HOST`, `ONTAP_USER` (default `admin`), `ONTAP_PASS`, `ONTAP_VERIFY_SSL` (default `false`)).
- Operational params via `argparse` with env-var fallbacks.
- Async jobs: `job_uuid = resp["job"]["uuid"]; client.poll_job(job_uuid)`.
- Logging via `logging` module - never `print()`.

## Ansible conventions

- Every ONTAP task: `use_rest: always`, `no_log: false`, all five connection params.
- `hosts: ontap`, `gather_facts: false`, `connection: local`.
- Collection pin: `netapp.ontap >= 22.12.0`.

## Terraform conventions

- `required_version >= 1.4`, provider `~> 2.5`.
- `connection_profiles` with `cx_profile_name = "cluster1"`.
- `sensitive = true` on password variables.
- Four files per module: `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`.

## Go conventions

- Import and use `go/ontap/ontapclient/ontap_client.go` — never build a new HTTP client.
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
