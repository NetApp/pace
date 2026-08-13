# Python Script Examples

Plain Python scripts that automate NetApp storage workflows over REST. Examples
are organized by the NetApp product they target — pick your product below.

| Product | Directory | Status |
|---------|-----------|--------|
| ONTAP | [`python/ontap/`](ontap/README.md) | 8 examples |
| Console | [`python/console/local/`](console/local/README.md) | Placeholder — no examples yet |

Each product directory carries its own README, dependency file, and shared
client module, so a product's examples can be copied without pulling in
anything from another product.

> **Catalog:** [`catalog.yaml`](../catalog.yaml) is the machine-readable index
> of every example, including which product it belongs to.

## Adding an example

Place new scripts under `python/<product>/` (ONTAP) or
`python/<product>/<deployment>/` where the product has deployment variants, and
add a matching entry to [`catalog.yaml`](../catalog.yaml). See
[CONTRIBUTING.md](../CONTRIBUTING.md) and
[`docs/example-template/`](../docs/example-template/README.md).
