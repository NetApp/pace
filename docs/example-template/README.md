# Example Templates

Skeleton files for adding a new NetApp storage automation example. Copy the
relevant directory into the top-level `python/`, `ansible/`, or `terraform/`
folder, rename files to match your use case, and fill in the logic.

## Python

```
python/
  example.py              # copy and rename to <use_case>.py
```

Uses the shared `ontap_client.py` already in `python/`. See existing scripts
for patterns (env-based config, polling, context manager).

## Ansible

```
ansible/
  example.yml             # copy and rename to <use_case>.yml
```

Uses inventory and `group_vars/` already in `ansible/`. All modules should
use FQCNs (`netapp.ontap.*`).

## Terraform

```
terraform/<use-case>/
  main.tf                 # provider + resources
  variables.tf            # input variables
  outputs.tf              # output values
  terraform.tfvars.example
```

Each use case is a self-contained root module. Copy the directory, rename it,
and add your resources.

## After adding

1. Update the parent `README.md` (e.g., `python/README.md`) with run instructions
2. Update the root `README.md` use-case table
3. Verify CI passes (`ruff`, `ansible-lint`, `terraform validate`)
