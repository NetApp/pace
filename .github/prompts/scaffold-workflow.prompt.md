# Scaffold a Multi-Step Orchestrio Workflow

Given a high-level goal (e.g. "provision an NFS volume", "collect cluster diagnostics"),
generate a complete multi-step Orchestrio workflow skeleton ready for customization.

> For ONTAP REST API conventions (endpoints, auth, headers, response shapes, async jobs),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Rules

1. Every workflow must have `name` (kebab-case), `version: "1"`, `description`, and a `steps` array.
2. Add an `env:` block listing every variable the workflow needs. Credentials must be empty
   placeholders (`""`); non-sensitive values may have sensible defaults.
3. Add a block comment above `env:` documenting each variable with `# VAR_NAME — purpose`.
4. When two or more HTTP steps share auth/headers/TLS, add a `defaults:` block (see
   `docs/ontap-api-patterns.md` for the standard ONTAP defaults template).
5. Step names must be `snake_case` matching `^[a-zA-Z_][a-zA-Z0-9_]*$`.
6. Use `{{ env.VAR }}` for credentials and host addresses — never hardcode secrets.
7. Wire step outputs with `{{ steps.<name>.<path> }}`.
8. For any ONTAP POST/PATCH that returns a job, add a `poll_job` step immediately after
   using the `ontap_poll_job.yaml` fragment.
9. Add `retry: { attempts: 3, delay_seconds: 5 }` on network-dependent GET steps.
10. Set `on_failure: continue` on non-critical steps (logging, summary); leave critical steps
    as the default `stop`.
11. End with a `shell` step that prints a human-readable summary using template expressions.
12. Add a brief `# ── Step N — description` comment before each step.
13. Prefer `include:` with fragments from `steps/` for operations that already have reusable
    fragments.

## Available step fragments in `steps/`

| Fragment | Step name | Purpose | Key outputs |
|----------|-----------|---------|-------------|
| `ontap_create_volume.yaml` | `create_volume` | POST a FlexVol volume | `body.job.uuid` |
| `ontap_poll_job.yaml` | `poll_job` | Poll an async job until completion | `body.state`, `body.message` |
| `ontap_get_volume.yaml` | `get_volume` | Fetch volume by name + SVM | `body.records.0.uuid` |
| `ontap_get_cluster.yaml` | `get_cluster` | Fetch cluster version info | `body.name`, `body.version.full` |
| `ontap_get_nodes.yaml` | `get_nodes` | List nodes with serial numbers | `body.num_records`, `body.records` |
| `ontap_discover_nodes.yaml` | `discover_nodes` | Discover available nodes (detailed) | `body.records` |

## Output format

1. Return a single YAML code block for the complete workflow.
2. Include `# ── Step N —` comments above each step.
3. After the YAML, list any new env vars the user must supply.
4. Suggest: `orchestrio validate <file>` and `orchestrio run --dry-run <file>`.

## Example

Goal: "Get cluster info and list all nodes."

```yaml
name: cluster-info
version: "1"
description: >-
  Get cluster version and list all nodes with serial numbers.

# ── Inputs ────────────────────────────────────────────────────────
# ONTAP_HOST — cluster management IP or hostname
# ONTAP_USER — admin username
# ONTAP_PASS — admin password
env:
  ONTAP_HOST: ""
  ONTAP_USER: "admin"
  ONTAP_PASS: ""

defaults:
  http:
    headers:
      Accept: "application/hal+json"
      X-Dot-Client-App: "orchestrio"
    username: "{{ env.ONTAP_USER }}"
    password: "{{ env.ONTAP_PASS }}"
    timeout: 30
    verify_ssl: false

steps:

  # ── Step 1 — Fetch cluster version ──────────────────────────────
  - include: ../steps/ontap_get_cluster.yaml

  # ── Step 2 — Print cluster name and version ─────────────────────
  - name: print_version
    type: shell
    config:
      command: >-
        echo "Cluster: {{ steps.get_cluster.body.name }} — {{ steps.get_cluster.body.version.full }}"

  # ── Step 3 — List all nodes ─────────────────────────────────────
  - include: ../steps/ontap_get_nodes.yaml

  # ── Step 4 — Print node count ──────────────────────────────────
  - name: print_nodes
    type: shell
    config:
      command: echo "Nodes in cluster — {{ steps.get_nodes.body.num_records }}"
```
