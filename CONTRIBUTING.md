# Contributing

Thanks for your interest in improving the ONTAP automation examples. This document
covers how to add new examples, what CI expects, and how the repo is organized.

---

## Repository Layout

```
python/               # Python script examples
ansible/              # Ansible playbook examples
terraform/            # Terraform module examples
yaml-workflows/       # Orchestrio YAML workflow executor
docs/                 # Shared documentation
.github/              # CI workflows, templates, review config
```

The primary investment area is **`python/`**, **`ansible/`**, and **`terraform/`**.
The `yaml-workflows/` directory contains the Orchestrio CLI executor and its
workflow definitions.

---

## Adding a New Example

### Required files

Each new use case should be implemented across all three tools where practical.
Use `docs/example-template/` as a starting point.

**Python** (`python/`):
- `<use_case>.py` — self-contained script
- Update `python/README.md` with a section for the new example

**Ansible** (`ansible/`):
- `<use_case>.yml` — playbook using `netapp.ontap` FQCNs
- Update `ansible/README.md` with a section for the new example

**Terraform** (`terraform/`):
- `<use_case>/main.tf` — provider + resources
- `<use_case>/variables.tf` — input variables with descriptions
- `<use_case>/outputs.tf` — useful output values
- `<use_case>/terraform.tfvars.example` — variable template
- Update `terraform/README.md` with a section for the new example

### Quality bar

Every example must:

- Be self-contained (copy one directory and it works)
- Never hardcode credentials — use env vars, Ansible Vault, or Terraform `sensitive`
- Include clear run instructions in the parent README
- Pass CI lint checks (see below)
- Follow the conventions of the target tool (idiomatic Python, Ansible FQCNs, HCL style)

### ONTAP API reference

All examples target ONTAP 9.8+ REST APIs. See
[docs/ontap-api-patterns.md](docs/ontap-api-patterns.md) for endpoint conventions,
auth patterns, async job handling, and standard environment variables.

---

## CI Expectations

PRs are validated by several GitHub Actions workflows:

| What | Workflow | Scope |
|------|----------|-------|
| **Python lint** | `validate-examples.yml` | `ruff check python/`, `ruff format --check python/`, `py_compile` |
| **Ansible lint** | `validate-examples.yml` | `ansible-playbook --syntax-check`, `ansible-lint` |
| **Terraform lint** | `validate-examples.yml` | `terraform fmt -check`, `terraform validate`, `tflint` |
| **Executor lint + tests** | `ci.yml` | `ruff check`, `pytest` (only on `yaml-workflows/` changes) |
| **Schema validation** | `pr-checks.yml` | YAML workflows against `yaml-workflows/workflow-spec/v1/schema.json` |
| **README check** | `pr-checks.yml` | Verifies `python/`, `ansible/`, `terraform/` each have a `README.md` |
| **Secret scan** | `review-bot.yml` | Blocks `.env` files and known secret patterns in diffs |

All lint checks are **hard gates** — PRs must pass before merge.

---

## Code Review

- All PRs require at least one approving review from a CODEOWNERS match
- Reviewers should verify: no hardcoded secrets, idiomatic code for the tool,
  README updated for new examples
- The Copilot review bot provides automated feedback on common patterns

---

## Naming Conventions

- **Python**: `snake_case` for filenames and functions (`cluster_info.py`, `nfs_provision.py`)
- **Ansible**: `snake_case` for playbook filenames (`cluster_info.yml`, `nfs_provision.yml`)
- **Terraform**: `kebab-case` for module directories (`cluster-info/`, `nfs-provision/`)
- **YAML workflows**: `snake_case` for workflow files and step names

---

## What Not to Change

The `yaml-workflows/` directory contains the Orchestrio executor and its workflow
definitions. Unless you are fixing a bug or security issue in the executor, avoid
modifying files under `yaml-workflows/executor/`. Schema changes under
`yaml-workflows/workflow-spec/` require careful backward-compatibility review.
