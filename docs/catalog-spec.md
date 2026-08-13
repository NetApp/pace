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
    product: ontap
    ontap_min: "9.8"
    owners: [57388sp, kxvya-git, mahatvagarg]
    status: verified
    tags: [cluster, read-only]
    verification:
      verified_by: 57388sp
      tested_at: "2026-05-29"
      ontap_version: "9.14.1P3"
      environment: ontap-simulator
    variants:
      python: { ... }
      ansible: { ... }
      terraform: { ... }
```

Each file contains a single `use_cases` list. Group variants (Python, Ansible,
Terraform, Go) under one use case when they automate the same storage task.

---

## Use case fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | yes | string | Unique kebab-case identifier (e.g. `cluster-info`, `nfs-provision`) |
| `description` | yes | string | One sentence — what storage problem this solves |
| `products` | yes | list | Supported NetApp products, for display (e.g. `ONTAP`, `FSxN`) |
| `product` | yes | string | Folder slug the example lives under — see [Products and deployments](#products-and-deployments) |
| `deployment` | when the product has variants | string | Deployment variant slug (e.g. `local` for `console`) |
| `ontap_min` | yes | string | Minimum ONTAP version (e.g. `"9.8"`) when `ONTAP` is listed |
| `owners` | yes | list | GitHub handles (no `@`) accountable for this use case — see [Owners](#owners) |
| `status` | yes | string | Lifecycle status — see [Status values](#status-values) |
| `tags` | no | list | Classification labels (e.g. `nfs`, `provisioning`, `read-only`) |
| `verification` | when `verified` | mapping | Owner attestation — see [Verification block](#verification-block) |
| `variants` | yes | map | One or more of `python`, `ansible`, `terraform`, `go` — see [Variant fields](#variant-fields) |

At least one variant (`python`, `ansible`, `terraform`, or `go`) is required per
use case. Not every use case needs all four — partial parity is recorded in the
catalog.

---

## Products and deployments

Examples are grouped on disk by the NetApp product they target. `product` is the
folder slug, and the validator requires every variant `path` to start with it:

| `product` | `deployment` | Path shape |
|-----------|--------------|------------|
| `ontap` | not used | `<tool>/ontap/…` |
| `console` | `local` | `<tool>/console/local/…` |

`products` stays as the human-facing display list (`[ONTAP]`); `product` is the
single slug that drives layout. A product listed in the table with a
`deployment` column value **must** set `deployment`; a product without variants
must **not** set it.

Adding a product or deployment means updating `VALID_PRODUCTS` /
`VALID_DEPLOYMENTS` in
[`scripts/validate_catalog.py`](../scripts/validate_catalog.py) — example
discovery itself is recursive and needs no change.

---

## Variant fields

Each key under `variants` (`python`, `ansible`, `terraform`, `go`) maps to:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `path` | yes | string | Path to script, playbook, Terraform module directory, or `main.go` (relative to repo root); must start with `<tool>/<product>/` |
| `command` | yes | string | Exact command to run the example, relative to `cwd` |
| `cwd` | yes | string | Working directory relative to repo root (e.g. `python/ontap`, `ansible/ontap`, `terraform/ontap/cluster-info`) |
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

## Owners

Each use case lists one or more GitHub handles (without `@`) in `owners`. These
are the people accountable for the example — not Pace repo maintainers by
default.

Contributors set `owners` when adding a new use case (typically including
themselves). For multi-variant use cases, list every owner responsible for a
variant.

---

## Verification block

Required when `status: verified`. Forbidden when `status` is `draft` or
`deprecated`. Records who attested end-to-end testing and where:

| Field | Required | Description |
|-------|----------|-------------|
| `verified_by` | yes | GitHub handle (no `@`) of the attesting owner — must appear in `owners` |
| `tested_at` | yes | ISO date (`YYYY-MM-DD`) of the end-to-end run |
| `ontap_version` | yes | Exact ONTAP version string from the cluster |
| `environment` | yes | One of: `ontap-simulator`, `ontap-select`, `real-cluster`, `cloud-volumes-ontap`, `other` |
| `test_report` | no | Link to PR or issue with Test Report evidence |
| `notes` | no | Short context (e.g. per-variant owner attribution) |

---

## Status values

| Status | Meaning |
|--------|---------|
| `draft` | New or changed — not yet owner-verified |
| `verified` | Attested by a listed owner as end-to-end tested; suitable to adapt |
| `deprecated` | Scheduled for removal or superseded — do not use for new work |

New contributions should set `status: draft` on first pull request. Maintainers
promote to `verified` after review and a populated Test Report (see
[`TESTING.md`](../TESTING.md)), adding a `verification` block where
`verified_by` is one of the listed `owners`.

---

## Naming conventions

| Element | Convention | Example |
|---------|------------|---------|
| Use case `id` | kebab-case | `snapmirror-test-failover` |
| Python `path` | `python/<product>/<snake_case>.py` | `python/ontap/nfs_provision.py` |
| Ansible `path` | `ansible/<product>/<snake_case>.yml` | `ansible/ontap/nfs_provision.yml` |
| Terraform `path` | `terraform/<product>/<kebab-case>/` | `terraform/ontap/nfs-provision/` |
| Go `path` | `go/<product>/<snake_case>/main.go` | `go/ontap/cluster_setup_basic/main.go` |

Products with deployment variants add that level too, e.g.
`python/console/local/<snake_case>.py`.

Paths must match existing repo naming rules in
[`CONTRIBUTING.md`](../CONTRIBUTING.md#naming-conventions).

---

## Example entry

```yaml
use_cases:
  - id: cluster-info
    description: Retrieve cluster version and list nodes with serial numbers
    products: [ONTAP]
    product: ontap
    ontap_min: "9.8"
    owners: [57388sp, kxvya-git, mahatvagarg]
    status: verified
    tags: [cluster, read-only]
    verification:
      verified_by: 57388sp
      tested_at: "2026-05-29"
      ontap_version: "9.14.1P3"
      environment: ontap-simulator
      notes: "Python: 57388sp, Ansible: kxvya-git, Terraform: mahatvagarg"
    variants:
      python:
        path: python/ontap/cluster_info.py
        command: "python cluster_info.py"
        cwd: python/ontap
        prerequisites:
          env: [ONTAP_HOST, ONTAP_PASS]
          setup: "pip install -r requirements.txt"
        inputs: []
        outputs: [cluster_version, nodes]

      ansible:
        path: ansible/ontap/cluster_info.yml
        command: "ansible-playbook -i inventory/hosts.yml cluster_info.yml"
        cwd: ansible/ontap
        prerequisites:
          env: [ontap_hostname, ontap_password]
          setup: "ansible-galaxy collection install -r requirements.yml"
        inputs: []
        outputs: [cluster_version, nodes]

      terraform:
        path: terraform/ontap/cluster-info
        command: "terraform apply"
        cwd: terraform/ontap/cluster-info
        prerequisites:
          env: []
          setup: "terraform init"
        inputs: [ontap_host, ontap_username, ontap_password]
        outputs: [cluster_name, ontap_version, nodes]
```

---

## Adding a new use case

1. Implement the example(s) under `<tool>/<product>/` — e.g. `python/ontap/`,
   `ansible/ontap/`, `terraform/ontap/`, `go/ontap/`
2. Add a `use_cases` entry (or extend an existing one with a new variant) in
   `catalog.yaml`, including `product` (and `deployment` where it applies)
3. Add a README section in the matching product README — e.g.
   `python/ontap/README.md`; see
   [README section template](../CONTRIBUTING.md#readme-section-template)
4. Include a one-sentence use-case justification in the pull request description

---

## Related documentation

- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution workflow and README template
- [`docs/example-template/README.md`](example-template/README.md) — skeleton for new examples
- [`TESTING.md`](../TESTING.md) — Test Report requirements
