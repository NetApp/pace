# Example Templates

Skeleton files for adding a new NetApp storage automation example. Copy the
relevant file into the directory for the product you are automating —
`<tool>/<product>/`, e.g. `python/ontap/` — rename to match your use case, and
fill in the logic. Never place examples at the tool root; it holds only a
product index README.

Paths below use `ontap` as the product. Products with deployment variants add
that level too, e.g. `python/console/local/`.

## Python

```
python/ontap/
  example.py              # copy and rename to <use_case>.py
```

Uses the shared `ontap_client.py` already in `python/ontap/` as a sibling
import. See existing scripts for patterns (env-based config, polling, context
manager).

## Ansible

```
ansible/ontap/
  example.yml             # copy and rename to <use_case>.yml
```

Uses the inventory and `group_vars/` already in `ansible/ontap/`. All modules
should use FQCNs (`netapp.ontap.*`).

## Go

```
go/ontap/<use_case>/
  main.go                 # copy and rename directory to <use_case>
```

Uses the shared `ontapclient` package already in `go/ontap/ontapclient/`,
imported as `github.com/netapp/pace/go/ontap/ontapclient`. All products share
the single module rooted at `go/`. See existing programs for patterns
(env-based config, `loadDotEnv()`, phase logging, `PollJob` for async calls).

## Terraform

```
terraform/ontap/<use-case>/
  main.tf                 # provider + resources
  variables.tf            # input variables
  outputs.tf              # output values
  terraform.tfvars.example
```

Each use case is a self-contained root module. Copy the directory, rename it,
and add your resources.

## After adding

1. Register the example in [`catalog.yaml`](../../catalog.yaml), including
   `product` — see [`docs/catalog-spec.md`](../catalog-spec.md) for required
   fields
2. Update the product `README.md` (e.g., `python/ontap/README.md`) using the
   [README section template](../../CONTRIBUTING.md#readme-section-template)
3. Update the root `README.md` use-case table
4. Verify CI passes (`ruff`, `ansible-lint`, `terraform validate`)

### Catalog entry snippet

Add a `use_cases` entry (or extend an existing use case with your variant).
Set `status: draft` on your first pull request:

```yaml
  - id: my-use-case          # kebab-case, matches your file/module name
    description: One sentence describing the storage task
    products: [ONTAP]         # display list
    product: ontap            # folder slug — must match the variant paths
    ontap_min: "9.8"
    owners: [your-github-handle]
    status: draft
    tags: [relevant, labels]
    variants:
      python:                 # omit keys you did not implement
        path: python/ontap/my_use_case.py
        command: "python my_use_case.py"
        cwd: python/ontap
        prerequisites:
          env: [ONTAP_HOST, ONTAP_PASS]
          setup: "pip install -r requirements.txt"
        inputs: [param_one]   # use [] if none
        outputs: [result_one]
      go:
        path: go/ontap/my_use_case/main.go
        command: "go run ."
        cwd: go/ontap/my_use_case
        prerequisites:
          env: [ONTAP_HOST, ONTAP_PASS]
          setup: "cd go && go mod download"
        inputs: [param_one]
        outputs: [result_one]
```

Replace `python` with `ansible` or `terraform` and adjust `path`, `command`,
`cwd`, and `prerequisites` for each variant you add. `command` and
`prerequisites.setup` are relative to `cwd`, so they do not repeat the product
directory. For a product with deployment variants, add `deployment: local` and
use `<tool>/console/local/…` paths.

When a maintainer promotes the entry to `verified`, they add a `verification`
block with `verified_by` set to one of the listed `owners`. See
[`docs/catalog-spec.md`](../catalog-spec.md#verification-block).
