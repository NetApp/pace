---
description: "Generate a complete ONTAP workflow — Python + Ansible + Terraform — for a storage task"
---

# Generate Complete ONTAP Workflow (All Three Tools)

You are generating a full automation example set for the **pace**
repository. Every use case in this repo ships Python, Ansible, and Terraform
implementations so users can compare side-by-side.

## Task

{task description}

## Reference Files

- [python/ontap_client.py](../../python/ontap_client.py) — shared Python REST client
- [python/nfs_provision.py](../../python/nfs_provision.py) — Python reference
- [ansible/nfs_provision.yml](../../ansible/nfs_provision.yml) — Ansible reference
- [ansible/cifs_provision.yml](../../ansible/cifs_provision.yml) — Ansible CIFS reference
- [terraform/nfs-provision/](../../terraform/nfs-provision/) — Terraform reference
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) — API endpoints, auth, async jobs
- [docs/example-template/](../../docs/example-template/) — skeleton files for all tools
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — naming, CI, quality bar

## Phase 1 — Clarify Inputs

Before generating any code, ask me for anything missing:
- SVM name, volume name/size, aggregate
- Protocol details (NFS client-match, CIFS share name, iSCSI IQN, etc.)
- Cluster hostname or IP
- Authentication approach
- Non-default options (snapshot policy, tiering, QoS, junction path)

## Phase 2 — API Sequence

Present a numbered list of ONTAP REST API calls in execution order.
For each:

| # | Method | Endpoint | Key Body/Query | Sync/Async | Why |
|---|--------|----------|----------------|------------|-----|

Rules:
- ONTAP REST only — no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ endpoints.
- Full paths (e.g. `/api/storage/volumes`).
- Include poll steps for async calls.

**Wait for my approval before Phase 3.**

## Phase 3 — Generate All Three Implementations

### 3A. Python — `python/<use_case>.py`

- `#!/usr/bin/env python3`, `from __future__ import annotations`
- Module docstring: steps, prerequisites, usage with CLI flags.
- `from ontap_client import OntapClient`
- `with OntapClient.from_env() as client:` (env: `ONTAP_HOST`, `ONTAP_PASS`)
- `argparse` with env-var fallbacks for operational params.
- `client.get/post/patch/delete` + `client.poll_job()` for async.
- `logging` module only (no `print()`).
- `if __name__ == "__main__":` with try/except guard.
- Type hints throughout. No hardcoded credentials.

### 3B. Ansible — `ansible/<use_case>.yml`

- `---` header with filename, description, usage comment.
- `hosts: ontap`, `gather_facts: false`, `connection: local`.
- `netapp.ontap.na_ontap_*` FQCNs, `use_rest: always`.
- All five connection params from variables on every task.
- `no_log: false`, `wait_for_completion: true`, `state: present/absent`.
- `vars:` for operational defaults (overridable with `-e`).
- Final `ansible.builtin.debug` summary. No hardcoded credentials.

### 3C. Terraform — `terraform/<use-case>/`

- `main.tf`: `required_version >= 1.4`, provider `NetApp/netapp-ontap ~> 2.5`,
  `connection_profiles` with `cx_profile_name = "cluster1"`.
- `variables.tf`: descriptions, types, `sensitive = true` for passwords.
- `outputs.tf`: meaningful outputs with descriptions.
- `terraform.tfvars.example`: placeholder values, no real credentials.
- `depends_on` where ordering matters.

## Phase 4 — Validate

For each implementation:
1. Exact commands to run it.
2. Error scenarios and how they are handled.
3. Cleanup / teardown instructions.

## Copyright header (required)

Every generated source file MUST start with the standard NetApp header in the
language-appropriate comment syntax. The `insert-license` pre-commit hook
will add it automatically, but include it from the start so AI-generated
output passes review on first read.

```text
© 2026 NetApp, Inc. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
See the NOTICE file in the repo root for trademark and attribution details.
```

Place after any shebang (`#!/usr/bin/env python3`), YAML directive (`---`),
or `<!DOCTYPE html>` line. Do **not** duplicate the full trademark text in
source files — it lives in [NOTICE](../../NOTICE) and the LICENSE appendix.
