# Copilot Instructions for Orchestrio

## Project overview

This repository contains ONTAP automation examples in Python, Ansible, and
Terraform. Each approach implements the same use cases so users can compare
side-by-side and pick the tool their team already knows.

## Repository layout

```
python/                 # Python script examples
ansible/                # Ansible playbook examples
terraform/              # Terraform module examples
docs/                   # guides and comparison documentation
```

## Coding conventions

- Python >= 3.11; use modern syntax (PEP 604 unions, f-strings, `match` where appropriate).
- Linter: `ruff` (line length 99, target py311). Run `ruff check python/`.
- All new Python code should have type hints.
- Never hardcode credentials — use env vars, Ansible Vault, or Terraform `sensitive`.
- Ansible playbooks use `netapp.ontap` FQCNs.
- Terraform modules use the `NetApp/netapp-ontap` provider.
