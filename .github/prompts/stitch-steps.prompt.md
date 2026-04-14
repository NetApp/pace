# Stitch Existing Step Fragments into a Workflow

Given a list of existing step fragments from `steps/` and a description of the desired
workflow, compose them into a complete workflow using `include:` directives with
appropriate `override:` blocks and template wiring.

> For ONTAP REST API conventions (endpoints, auth, headers, response shapes, async jobs),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Available step fragments

| Fragment file | Step name | What it does | Key outputs |
|---------------|-----------|--------------|-------------|
| `ontap-create-volume.yaml` | `create_volume` | POST a FlexVol volume | `body.job.uuid` |
| `ontap-poll-job.yaml` | `poll_job` | Poll async job to completion | `body.state`, `body.message` |
| `ontap-get-volume.yaml` | `get_volume` | Fetch volume by name + SVM | `body.records.0.uuid` |
| `ontap-get-cluster.yaml` | `get_cluster` | Fetch cluster version | `body.name`, `body.version.full` |
| `ontap-get-nodes.yaml` | `get_nodes` | List nodes + serial numbers | `body.num_records`, `body.records` |
| `ontap-discover-nodes.yaml` | `discover_nodes` | Discover available nodes (detailed) | `body.records` |

## Rules

1. Use `include:` to reference fragments. Paths are relative to the workflow file:
   ```yaml
   - include: ../steps/ontap-get-cluster.yaml
   ```
2. Use `override:` to customize a fragment. `config` is **deep-merged** (fragment values
   are the base, override values win). Other fields (`name`, `retry`, `on_failure`) **replace**.
3. When the same fragment is used more than once, **always** override `name` to give each
   instance a unique step name.
4. Wire outputs from included steps using `{{ steps.<step_name>.<path> }}` where
   `<step_name>` is the fragment's `name:` field (or the overridden name).
5. After any included step that triggers an async ONTAP job, add a `poll_job` include
   with the job UUID wired from the previous step.
6. Add a `defaults:` block for shared HTTP config so fragments inherit auth automatically —
   fragments are designed to omit auth fields.
7. Every workflow needs `name`, `version: "1"`, `description`, `env`, and `steps`.
8. Add inline steps (type: `shell` or `http`) where no existing fragment fits.
9. End with a summary `shell` step that echoes the result using template expressions.

## Output format

1. Return a single YAML code block for the complete workflow.
2. After the YAML, list the env vars the user must supply.
3. Suggest: `orchestrio validate <file>` then `orchestrio run --dry-run <file>`.

## Example

Goal: "Create a volume and verify it exists."

Fragments used: `ontap-create-volume.yaml`, `ontap-poll-job.yaml`, `ontap-get-volume.yaml`.

```yaml
name: create-and-verify-volume
version: "1"
description: >-
  Create an ONTAP FlexVol volume, poll until the job completes,
  then fetch the volume to confirm it exists.

# ── Inputs ────────────────────────────────────────────────────────
# ONTAP_HOST   — cluster management IP or hostname
# ONTAP_USER   — admin username
# ONTAP_PASS   — admin password
# SVM_NAME     — SVM to create the volume on
# VOLUME_NAME  — name of the new volume
# VOLUME_SIZE  — size (e.g. 100MB, 1GB)
# AGGR_NAME    — aggregate to place the volume on
env:
  ONTAP_HOST:  ""
  ONTAP_USER:  "admin"
  ONTAP_PASS:  ""
  SVM_NAME:    "vs0"
  VOLUME_NAME: "test_vol_01"
  VOLUME_SIZE: "100MB"
  AGGR_NAME:   ""

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

  # ── Step 1 — Create the volume ──────────────────────────────────
  - include: ../steps/ontap-create-volume.yaml

  # ── Step 2 — Poll creation job ─────────────────────────────────
  - include: ../steps/ontap-poll-job.yaml
    override:
      name: track_create_job
      config:
        url: "https://{{ env.ONTAP_HOST }}/api/cluster/jobs/{{ steps.create_volume.body.job.uuid }}?fields=state,message&return_timeout=120"
        poll:
          interval_seconds: 5

  # ── Step 3 — Fetch the volume to confirm it exists ──────────────
  - include: ../steps/ontap-get-volume.yaml

  # ── Step 4 — Print confirmation ────────────────────────────────
  - name: print_result
    type: shell
    config:
      command: >-
        echo "Volume '{{ env.VOLUME_NAME }}' created — UUID: {{ steps.get_volume.body.records.0.uuid }}"
```
