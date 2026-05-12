# Contributing

Thanks for your interest in improving the NetApp storage automation examples in
this repository. This document covers how to add new examples, what CI expects,
and how the repo is organized.

---

## Contributor License Agreement

Before any code you contribute can be reviewed or merged, you must sign and
submit NetApp's
[Corporate Contributor License Agreement (CCLA)](https://netapp.tap.thinksmart.com/prod/Portal/ShowWorkFlow/AnonymousEmbed/3d2f3aa5-9161-4970-997d-e482b0b033fa).

When completing the form, specify one of the following for the **Project Name**
field:

- `NetApp/pace`
- `https://github.com/NetApp/pace`

> **Important:** NetApp will **not** review your pull request or any code
> submitted in it until the CCLA is on file with NetApp Legal.

---

## Repository Layout

```
python/               # Python script examples
ansible/              # Ansible playbook examples
terraform/            # Terraform module examples
docs/                 # Shared documentation
.github/              # CI workflows, templates, review config
TESTING.md            # What to capture in the PR Test Report
```

---

## Adding a New Example

### Required files

Each new use case should be implemented across all three tools where practical.
Use `docs/example-template/` as a starting point.

**Python** (`python/`):
- `<use_case>.py` - self-contained script
- Update `python/README.md` with a section for the new example

**Ansible** (`ansible/`):
- `<use_case>.yml` - playbook using `netapp.ontap` FQCNs
- Update `ansible/README.md` with a section for the new example

**Terraform** (`terraform/`):
- `<use_case>/main.tf` - provider + resources
- `<use_case>/variables.tf` - input variables with descriptions
- `<use_case>/outputs.tf` - useful output values
- `<use_case>/terraform.tfvars.example` - variable template
- Update `terraform/README.md` with a section for the new example

### Quality bar

Every example must:

- Be self-contained (copy one directory and it works)
- Never hardcode credentials - use env vars, Ansible Vault, or Terraform `sensitive`
- Include clear run instructions in the parent README
- Pass CI lint checks (see below)
- Follow the conventions of the target tool (idiomatic Python, Ansible FQCNs, HCL style)
- Carry the standard NetApp copyright header (see *Copyright headers* below)

### Copyright headers

Every source file (`*.py`, `*.yml`/`*.yaml`, `*.tf`, `*.sh`, `*.html`) must
begin with the short NetApp header in the language-appropriate comment
syntax. The full trademark notice lives in [NOTICE](NOTICE) and the LICENSE
appendix; source headers stay short and reference it.

```text
© 2026 NetApp, Inc. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
See the NOTICE file in the repo root for trademark and attribution details.
```

The `insert-license` pre-commit hook (configured in
[.pre-commit-config.yaml](.pre-commit-config.yaml)) inserts and verifies the
header automatically; CI rejects PRs that drop it. Exempt files: Markdown,
`requirements.*`, `ansible/inventory/*`, `ansible/group_vars/*`, `*.example`,
and `dependabot.yml` - all covered by the root [NOTICE](NOTICE).

> **Testing:** Every PR that touches `python/`, `ansible/`, or `terraform/`
> must include a populated **Test Report** in the PR body - see
> [TESTING.md](TESTING.md) for what to capture (environment, platform
> version, first-run output, idempotency / re-run check, teardown). A
> soft-gate workflow applies a `needs-test-report` label until the
> section is filled in.
>
> CI continues to validate lint, format, syntax, and secrets only - the
> end-to-end run evidence is contributor-supplied.

### Platform API reference

Today's examples target ONTAP 9.8+ REST APIs. See
[docs/ontap-api-patterns.md](docs/ontap-api-patterns.md) for endpoint conventions,
auth patterns, async job handling, and standard environment variables.

---

## Local Development Workflow

### Prerequisites

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| **Python** | >= 3.11 | Linting | [python.org](https://www.python.org/downloads/) or `brew install python@3.11` |
| **make** | any | Task runner | Pre-installed on macOS/Linux |
| **pre-commit** | any | Git hook manager | `pip install pre-commit` or `brew install pre-commit` |

Optional (only needed for example validation):

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| **Ansible** | any | Ansible example validation | `pip install ansible ansible-lint` |
| **Terraform** | >= 1.7 | Terraform example validation | [terraform.io](https://developer.hashicorp.com/terraform/install) or `brew install terraform` |
| **tflint** | any | Terraform linting | [github.com/terraform-linters/tflint](https://github.com/terraform-linters/tflint) |

`make install` automatically creates a `.venv/` and installs **ruff**
inside it - you do not need to install it manually.

### First-time setup

```bash
# Create venv and install dev deps (ruff)
make install

# Install pre-commit hooks (auto-runs checks on commit and push)
make hooks
```

### Editor setup (Cursor / VS Code)

Both Cursor and VS Code read the `.vscode/` config shipped with this repo.
Open the repo and accept the **recommended extensions** prompt, or search
`@recommended` in the Extensions sidebar. The workspace ships `.vscode/extensions.json` with:

| Extension | What it does |
|-----------|-------------|
| **Ruff** (`charliermarsh.ruff`) | Python lint + format on save (replaces black, isort, flake8) |
| **YAML** (`redhat.vscode-yaml`) | YAML syntax highlighting and validation |
| **Terraform** (`hashicorp.terraform`) | HCL formatting and validation |
| **Ansible** (`redhat.ansible`) | Playbook syntax and lint |
| **EditorConfig** (`editorconfig.editorconfig`) | Applies `.editorconfig` indent/whitespace rules |

The workspace `.vscode/settings.json` configures:
- **Python format-on-save** via Ruff (matches CI exactly)
- **Terraform format-on-save** via the Terraform extension
- **Python interpreter** pointed at `.venv/bin/python` (from `make install`)

No manual formatter configuration needed - just save the file and it formats.

### Running checks locally

Use the Makefile to mirror exactly what CI runs:

```bash
make help                # Show all available targets
make ci                  # Run lint (mirrors ci.yml)
make lint                # Ruff lint + format check
make ansible-lint        # Ansible syntax-check + ansible-lint
make terraform-validate  # Terraform fmt, validate, tflint
```

Run `make ci` before pushing to catch issues before they hit CI.

### Using Docker

If you prefer not to install toolchains locally, use the provided
Dockerfile to get a reproducible environment:

```bash
# Build the dev container
make docker-build

# Run all CI checks inside the container
make docker-ci

# Or use docker compose for an interactive shell
docker compose run --rm dev bash
```

The container includes Python 3.11, Ruff, pre-commit, Ansible, ansible-lint,
Terraform, and tflint - everything CI expects.

### Pre-commit hooks

The `.pre-commit-config.yaml` runs automatically on every commit:

| Hook | Stage | What it catches |
|------|-------|-----------------|
| `ruff` (lint + fix) | `pre-commit` | Python lint issues (auto-fixes safe ones) |
| `ruff-format` | `pre-commit` | Python formatting |
| `commitlint` | `commit-msg` | Conventional commit message violations |
| `check-yaml` | `pre-commit` | YAML syntax errors |
| `trufflehog` | `pre-push` | Leaked secrets (runs before push, not every commit) |

---

## CI Expectations

PRs are validated by GitHub Actions workflows:

| What | Workflow | Trigger | Scope |
|------|----------|---------|-------|
| **Python lint + format** | `ci.yml` | Every push & PR | `ruff check` + `ruff format --check` on `python/` |
| **README check** | `ci.yml` | Every push & PR | Verifies `python/`, `ansible/`, `terraform/` each have a `README.md` |
| **Commit lint** | `pr-guard.yml` | PRs only | Conventional commit messages via commitlint |
| **Secret scan** | `pr-guard.yml` | PRs only | TruffleHog scans PR diff for leaked credentials |
| **YAML syntax** | `pr-guard.yml` | PRs only | Parse-checks changed YAML files |
| **Ansible lint** | `validate-examples.yml` | `ansible/**` changes | `ansible-playbook --syntax-check`, `ansible-lint` |
| **Terraform lint** | `validate-examples.yml` | `terraform/**` changes | `terraform fmt -check`, `terraform validate`, `tflint` |
| **Test Report check** | `test-report-check.yml` | PRs only | Soft gate: labels PR `needs-test-report` if the body's Test Report section is unfilled (see [TESTING.md](TESTING.md)) |

All checks except the Test Report check are **hard gates** - PRs must
pass them before merge. The Test Report check is informational and
reviewer-enforced.

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
- **Artifacts** use the pattern `pace-<version>.<ext>` (e.g. `pace-0.2.0.tar.gz`)
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

**Scopes:** `python`, `ansible`, `terraform`, `docs`, `ci`, `deps`
