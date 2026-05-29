# Example Catalog Specification

The Pace repository maintains a machine-readable index of every automation
example in [`catalog.yaml`](../catalog.yaml) at the repo root. This document
defines the required fields and conventions for catalog entries.

> **Status:** Catalog entries are validated by CI via
> [`scripts/validate_catalog.py`](../scripts/validate_catalog.py). Run
> `make validate-catalog` locally before pushing.

---

## Purpose

The catalog ensures every script, playbook, and Terraform module is:

- **Discoverable** — grouped by storage use case, not buried in a flat directory
- **Documented** — prerequisites, run commands, and inputs/outputs are explicit
- **Curated** — new entries carry a lifecycle status (`draft` → `verified`)

Ownership, license, and maintainers inherit from repo-level
[`CODEOWNERS`](../.github/CODEOWNERS) and [`LICENSE`](../LICENSE).

---

## Top-level structure

```yaml
use_cases:
  - id: cluster-info
    description: ...
    products: [ONTAP]
    ontap_min: "9.8"
    status: verified
    tags: [cluster, read-only]
    variants:
      python: { ... }
      ansible: { ... }
      terraform: { ... }
```

Each file contains a single `use_cases` list. Group variants (Python, Ansible,
Terraform) under one use case when they automate the same storage task.

---

## Use case fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | yes | string | Unique kebab-case identifier (e.g. `cluster-info`, `nfs-provision`) |
| `description` | yes | string | One sentence — what storage problem this solves |
| `products` | yes | list | Supported NetApp products (e.g. `ONTAP`, `FSxN`) |
| `ontap_min` | yes | string | Minimum ONTAP version (e.g. `"9.8"`) when `ONTAP` is listed |
| `status` | yes | string | Lifecycle status — see [Status values](#status-values) |
| `tags` | no | list | Classification labels (e.g. `nfs`, `provisioning`, `read-only`) |
| `variants` | yes | map | One or more of `python`, `ansible`, `terraform` — see [Variant fields](#variant-fields) |

At least one variant (`python`, `ansible`, or `terraform`) is required per use
case. Not every use case needs all three — partial parity is recorded in the
catalog.

---

## Variant fields

Each key under `variants` (`python`, `ansible`, `terraform`) maps to:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `path` | yes | string | Path to script, playbook, or Terraform module directory (relative to repo root) |
| `command` | yes | string | Exact command to run the example |
| `cwd` | yes | string | Working directory relative to repo root (e.g. `python`, `ansible`, `terraform/cluster-info`) |
| `prerequisites.setup` | yes | string | Install or init step (e.g. `pip install -r requirements.txt`) |
| `prerequisites.env` | yes | list | Environment variables or Ansible vars required — use `[]` if none |
| `inputs` | yes | list | Parameter names the example accepts — use `[]` if none |
| `outputs` | yes | list | Values the example produces (stdout, register vars, Terraform outputs) |

### Credentials

List every credential or connection variable in `prerequisites.env`. Do not
leave authentication implicit. Examples:

- Python: `ONTAP_HOST`, `ONTAP_PASS`
- Ansible: `ontap_hostname`, `ontap_password` (from `group_vars/`)
- Terraform: `[]` at the variant level when credentials are supplied via
  `terraform.tfvars` — list the variable names in `inputs` instead

---

## Status values

| Status | Meaning |
|--------|---------|
| `draft` | New or in-progress — not yet reviewed for production use |
| `verified` | Reviewed, tested, and suitable for adaptation |
| `deprecated` | Scheduled for removal or superseded — do not use for new work |

New contributions should set `status: draft` on first pull request. Maintainers
promote to `verified` after review and a populated Test Report (see
[`TESTING.md`](../TESTING.md)).

---

## Naming conventions

| Element | Convention | Example |
|---------|------------|---------|
| Use case `id` | kebab-case | `snapmirror-test-failover` |
| Python `path` | `python/<snake_case>.py` | `python/nfs_provision.py` |
| Ansible `path` | `ansible/<snake_case>.yml` | `ansible/nfs_provision.yml` |
| Terraform `path` | `terraform/<kebab-case>/` | `terraform/nfs-provision/` |

Paths must match existing repo naming rules in
[`CONTRIBUTING.md`](../CONTRIBUTING.md#naming-conventions).

---

## Example entry

```yaml
use_cases:
  - id: cluster-info
    description: Retrieve cluster version and list nodes with serial numbers
    products: [ONTAP]
    ontap_min: "9.8"
    status: verified
    tags: [cluster, read-only]
    variants:
      python:
        path: python/cluster_info.py
        command: "python cluster_info.py"
        cwd: python
        prerequisites:
          env: [ONTAP_HOST, ONTAP_PASS]
          setup: "pip install -r requirements.txt"
        inputs: []
        outputs: [cluster_version, nodes]

      ansible:
        path: ansible/cluster_info.yml
        command: "ansible-playbook -i inventory/hosts.yml cluster_info.yml"
        cwd: ansible
        prerequisites:
          env: [ontap_hostname, ontap_password]
          setup: "ansible-galaxy collection install -r requirements.yml"
        inputs: []
        outputs: [cluster_version, nodes]

      terraform:
        path: terraform/cluster-info
        command: "terraform apply"
        cwd: terraform/cluster-info
        prerequisites:
          env: []
          setup: "terraform init"
        inputs: [ontap_host, ontap_username, ontap_password]
        outputs: [cluster_name, ontap_version, nodes]
```

---

## Adding a new use case

1. Implement the example(s) in `python/`, `ansible/`, and/or `terraform/`
2. Add a `use_cases` entry (or extend an existing one with a new variant) in
   `catalog.yaml`
3. Add a README section in the matching tool README — see
   [README section template](../CONTRIBUTING.md#readme-section-template)
4. Include a one-sentence use-case justification in the pull request description

---

## Related documentation

- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution workflow and README template
- [`docs/example-template/README.md`](example-template/README.md) — skeleton for new examples
- [`TESTING.md`](../TESTING.md) — Test Report requirements
