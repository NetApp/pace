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

1. Register the example in [`catalog.yaml`](../../catalog.yaml) — see
   [`docs/catalog-spec.md`](../catalog-spec.md) for required fields
2. Update the parent `README.md` (e.g., `python/README.md`) using the
   [README section template](../../CONTRIBUTING.md#readme-section-template)
3. Update the root `README.md` use-case table
4. Verify CI passes (`ruff`, `ansible-lint`, `terraform validate`)

### Catalog entry snippet

Add a `use_cases` entry (or extend an existing use case with your variant).
Set `status: draft` on your first pull request:

```yaml
  - id: my-use-case          # kebab-case, matches your file/module name
    description: One sentence describing the storage task
    products: [ONTAP]
    ontap_min: "9.8"
    owners: [your-github-handle]
    status: draft
    tags: [relevant, labels]
    variants:
      python:                 # omit keys you did not implement
        path: python/my_use_case.py
        command: "python my_use_case.py"
        cwd: python
        prerequisites:
          env: [ONTAP_HOST, ONTAP_PASS]
          setup: "pip install -r requirements.txt"
        inputs: [param_one]   # use [] if none
        outputs: [result_one]
```

Replace `python` with `ansible` or `terraform` and adjust `path`, `command`,
`cwd`, and `prerequisites` for each variant you add.

When a maintainer promotes the entry to `verified`, they add a `verification`
block with `verified_by` set to one of the listed `owners`. See
[`docs/catalog-spec.md`](../catalog-spec.md#verification-block).
