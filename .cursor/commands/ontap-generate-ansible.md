<!-- Generated from ai/ontap/generate-ansible.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# Generate Ansible Storage Playbook

You are generating an Ansible playbook for the **pace** repository.
The playbook automates a NetApp ONTAP storage task using the `netapp.ontap`
collection, which calls exclusively REST APIs.

## Task

{task description}

## Reference Files

Use these repository files as the authoritative source for conventions:

- [ansible/ontap/nfs_provision.yml](../../ansible/ontap/nfs_provision.yml) - NFS reference implementation
- [ansible/ontap/cifs_provision.yml](../../ansible/ontap/cifs_provision.yml) - CIFS reference implementation
- [ansible/ontap/group_vars/ontap.yml.example](../../ansible/ontap/group_vars/ontap.yml.example) - variable defaults
- [ansible/ontap/inventory/hosts.yml](../../ansible/ontap/inventory/hosts.yml) - inventory structure
- [ansible/ontap/requirements.yml](../../ansible/ontap/requirements.yml) - collection version pin
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - API endpoints, auth, async jobs
- [docs/example-template/ansible/example.yml](../../docs/example-template/ansible/example.yml) - skeleton
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - naming, CI, quality bar

## Step 1 - Clarify Inputs

Before writing YAML, identify what information is missing and ask me.
Common inputs: SVM name, volume name/size, aggregate, protocol details,
cluster hostname, special options (snapshot policy, QoS, junction path).

## Step 2 - API Sequence

Even though Ansible modules abstract the API, list the underlying REST calls
and map each to its `netapp.ontap` module:

| # | REST Endpoint | Module | Key Parameters | Why |
|---|---------------|--------|----------------|-----|

Rules:
- REST only - `use_rest: always` on every ONTAP module.
- Target ONTAP 9.8+.
- Fully-qualified collection names: `netapp.ontap.na_ontap_*`.
- Collection version: `netapp.ontap >= 22.12.0`.

Wait for my confirmation before generating the playbook.

## Step 3 - Generate Playbook

File: `ansible/<product>/<use_case>.yml` (snake_case filename)

### Mandatory conventions

```yaml
---
# <use_case>.yml - Brief description.
#
# Usage:
#   ansible-playbook -i inventory/hosts.yml <use_case>.yml
#
# Override variables:
#   ansible-playbook -i inventory/hosts.yml <use_case>.yml \
#       -e variable_name=value
```

- Play definition:
  ```yaml
  - name: "<Descriptive Play Name>"
    hosts: ontap
    gather_facts: false
    connection: local
  ```
- `vars:` section for operational defaults (overridable with `-e`).
- Every ONTAP task MUST include ALL of these parameters:
  ```yaml
  hostname: "{{ ontap_hostname }}"
  username: "{{ ontap_username }}"
  password: "{{ ontap_password }}"
  https: "{{ ontap_https }}"
  validate_certs: "{{ ontap_validate_certs }}"
  use_rest: always
  ```
- `no_log: false` explicitly on every ONTAP task.
- `state: present` for creates, `state: absent` for deletes.
- `wait_for_completion: true` where the module supports it.
- `register:` to capture results needed by later tasks.
- Final task: `ansible.builtin.debug` with a summary message.
- No hardcoded credentials.

### Connection variables (from `group_vars/ontap.yml`)

```yaml
ontap_hostname: <cluster-ip>
ontap_username: admin
ontap_password: <from vault>
ontap_https: true
ontap_validate_certs: false
```

### Provisioning variables

```yaml
svm_name, volume_name, volume_size, volume_size_unit, aggregate_name,
client_match (NFS), share_name (CIFS), etc.
```

## Step 4 - Validate

After the playbook, provide:
1. Exact `ansible-playbook` command to run it.
2. Idempotency behavior - what happens on re-run for each task.
3. Teardown playbook or reversal instructions.

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
source files - it lives in [NOTICE](../../NOTICE) and the LICENSE appendix.
