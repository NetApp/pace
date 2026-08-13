# Terraform Module Examples

Self-contained Terraform root modules that automate NetApp storage workflows.
Examples are organized by the NetApp product they target — pick your product
below.

| Product | Directory | Status |
|---------|-----------|--------|
| ONTAP | [`terraform/ontap/`](ontap/README.md) | 3 modules |
| Console | [`terraform/console/local/`](console/local/README.md) | Placeholder — no modules yet |

Every module remains an independent root module with its own provider block and
state, so you can grab a single directory without pulling the whole repo.

> **Catalog:** [`catalog.yaml`](../catalog.yaml) is the machine-readable index
> of every example, including which product it belongs to.

## Adding an example

Place new modules under `terraform/<product>/<use-case>/` (ONTAP) or
`terraform/<product>/<deployment>/<use-case>/` where the product has deployment
variants, and add a matching entry to [`catalog.yaml`](../catalog.yaml). See
[CONTRIBUTING.md](../CONTRIBUTING.md) and
[`docs/example-template/`](../docs/example-template/README.md).
