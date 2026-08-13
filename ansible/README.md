# Ansible Playbook Examples

Ansible playbooks that automate NetApp storage workflows. Examples are organized
by the NetApp product they target — pick your product below.

| Product | Directory | Status |
|---------|-----------|--------|
| ONTAP | [`ansible/ontap/`](ontap/README.md) | 8 playbooks |
| Console | [`ansible/console/local/`](console/local/README.md) | Placeholder — no playbooks yet |

Each product directory carries its own README, `requirements.yml`, inventory,
and `group_vars`, so a product's playbooks can be run without pulling in
collections or connection variables from another product.

> **Catalog:** [`catalog.yaml`](../catalog.yaml) is the machine-readable index
> of every example, including which product it belongs to.

## Adding an example

Place new playbooks under `ansible/<product>/` (ONTAP) or
`ansible/<product>/<deployment>/` where the product has deployment variants, and
add a matching entry to [`catalog.yaml`](../catalog.yaml). See
[CONTRIBUTING.md](../CONTRIBUTING.md) and
[`docs/example-template/`](../docs/example-template/README.md).
