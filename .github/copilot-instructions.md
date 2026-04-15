# Copilot Instructions for Orchestrio

## Project overview

This repository contains ONTAP automation examples in Python, Ansible, and
Terraform. Each approach implements the same use cases so users can compare
side-by-side and pick the tool their team already knows.

## Repository layout

```
python/                 # Python script examples (snake_case files)
ansible/                # Ansible playbook examples (snake_case files)
terraform/              # Terraform module examples (kebab-case dirs)
docs/                   # Guides, API patterns, comparison docs
.github/prompts/        # Reusable Copilot prompts for workflow generation
```

## Reusable Prompts

This repository ships reusable prompt files in `.github/prompts/`. Use them
from Copilot Chat to generate new workflows that already follow every
convention:

| Prompt | What it does |
|--------|-------------|
| `generate-python` | Generate a Python script using `ontap_client.OntapClient` |
| `generate-ansible` | Generate an Ansible playbook using `netapp.ontap` modules |
| `generate-terraform` | Generate a Terraform module using `NetApp/netapp-ontap` provider |
| `generate-workflow` | Generate all three implementations at once |
| `plan-api-sequence` | Design the REST API call sequence before writing code |
| `review-contribution` | Review code against CI, naming, and PR requirements |

## Coding conventions

- Python >= 3.11; use modern syntax (PEP 604 unions, f-strings, `match` where appropriate).
- Linter: `ruff` (line length 99, target py311). Run `ruff check python/`.
- All new Python code should have type hints.
- Never hardcode credentials — use env vars, Ansible Vault, or Terraform `sensitive`.
- Ansible playbooks use `netapp.ontap` FQCNs with `use_rest: always`.
- Terraform modules use the `NetApp/netapp-ontap` provider `~> 2.5`.

## ONTAP API rules

- Use ONLY ONTAP REST APIs — no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ REST endpoints.
- See `docs/ontap-api-patterns.md` for endpoints, auth, async job handling.

## Python conventions

- Import and use `python/ontap_client.py` — never build a new HTTP client.
- Authenticate via `OntapClient.from_env()` (reads `ONTAP_HOST`, `ONTAP_PASS`).
- Operational params via `argparse` with env-var fallbacks.
- Async jobs: `client.poll_job(resp["job"]["uuid"])`.
- Logging via `logging` module — never `print()`.

## Ansible conventions

- Every ONTAP task: `use_rest: always`, `no_log: false`, all five connection params.
- `hosts: ontap`, `gather_facts: false`, `connection: local`.
- Collection pin: `netapp.ontap >= 22.12.0`.

## Terraform conventions

- `required_version >= 1.4`, provider `~> 2.5`.
- `connection_profiles` with `cx_profile_name = "cluster1"`.
- `sensitive = true` on password variables.
- Four files per module: `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`.
