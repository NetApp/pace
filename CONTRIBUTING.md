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

| What | Workflow | Trigger | Scope |
|------|----------|---------|-------|
| **Python lint** | `validate-examples.yml` | Every PR | `ruff check python/`, `ruff format --check python/`, `py_compile` |
| **Ansible lint** | `validate-examples.yml` | Every PR | `ansible-playbook --syntax-check`, `ansible-lint` |
| **Terraform lint** | `validate-examples.yml` | Every PR | `terraform fmt -check`, `terraform validate`, `tflint` |
| **Executor lint + tests** | `pr-checks.yml` | Every PR | `ruff check` on executor + `python/`, `pytest` on executor tests |
| **Executor deep CI** | `ci.yml` | `yaml-workflows/**` changes only | Additional `ruff` + `pytest` run scoped to the executor |
| **Schema validation** | `pr-checks.yml` | Every PR | YAML workflows against `yaml-workflows/workflow-spec/v1/schema.json` |
| **README check** | `pr-checks.yml` | Every PR | Verifies `python/`, `ansible/`, `terraform/` each have a `README.md` |
| **Secret scan** | `review-bot.yml` | Every PR | Blocks `.env` files and known secret patterns in diffs |

All lint checks are **hard gates** — PRs must pass before merge.

---

## Code Review

- All PRs require at least one approving review from a CODEOWNERS match
- Reviewers should verify: no hardcoded secrets, idiomatic code for the tool,
  README updated for new examples
- The Copilot review bot provides automated feedback on common patterns

---

## Naming Conventions

When in doubt, follow the pattern used by existing files in the same directory.

### File and directory naming

| Area | Convention | Examples |
|------|-----------|----------|
| **Python files** | `snake_case` | `cluster_info.py`, `nfs_provision.py` |
| **Ansible playbooks** | `snake_case` | `cluster_info.yml`, `nfs_provision.yml` |
| **Terraform modules** | `kebab-case` directories | `cluster-info/`, `nfs-provision/` |
| **YAML workflow files** | `kebab-case` | `cluster-info.yaml`, `nfs-provision.yaml` |
| **GitHub workflow files** | `kebab-case` `.yml` | `pr-checks.yml`, `validate-examples.yml` |
| **Documentation** | `kebab-case` `.md` for multi-word | `ontap-api-patterns.md` |
| **Shell scripts** | `kebab-case` for multi-word | `setup-branch-protection.sh` |
| **Community files** | `UPPERCASE.md` | `CONTRIBUTING.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md` |

### Branch naming

| Branch type | Pattern | Example |
|-------------|---------|---------|
| Feature | `feature/<short-description>` | `feature/add-snapmirror-example` |
| Bug fix | `fix/<short-description>` | `fix/nfs-provision-timeout` |
| Release | `release/<version>` | `release/0.2.0` |

The default branch is `main`. All PRs target `main`.

### Tags and releases

- **Tags** follow [Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH` (e.g. `v0.2.0`)
- **Release titles** omit the `v` prefix: `0.2.0`
- **Artifacts** use the pattern `orchestrio-<version>.<ext>` (e.g. `orchestrio-0.2.0.tar.gz`)
- All notable changes are recorded in [CHANGELOG.md](CHANGELOG.md)

### Commit messages

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:** `build`, `chore`, `ci`, `doc`, `feat`, `fix`, `perf`, `refactor`,
`revert`, `style`, `test`

**Scopes:** `python`, `ansible`, `terraform`, `executor`, `workflows`, `docs`,
`ci`, `deps`

---

## What Not to Change

The `yaml-workflows/` directory contains the Orchestrio executor and its workflow
definitions. Unless you are fixing a bug or security issue in the executor, avoid
modifying files under `yaml-workflows/executor/`. Schema changes under
`yaml-workflows/workflow-spec/` require careful backward-compatibility review.
