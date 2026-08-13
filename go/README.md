# Go Examples

Go programs that automate NetApp storage workflows over REST. Examples are
organized by the NetApp product they target — pick your product below.

| Product | Directory | Status |
|---------|-----------|--------|
| ONTAP | [`go/ontap/`](ontap/README.md) | 5 programs |
| Console | [`go/console/local/`](console/local/README.md) | Placeholder — no programs yet |

All products share the single Go module rooted at `go/` (module
`github.com/netapp/pace/go`), so `go mod download` and `go vet ./...` are run
from `go/`. Each product supplies its own client package — ONTAP programs import
`github.com/netapp/pace/go/ontap/ontapclient`.

> **Catalog:** [`catalog.yaml`](../catalog.yaml) is the machine-readable index
> of every example, including which product it belongs to.

## Adding an example

Place new programs under `go/<product>/<use_case>/main.go` (ONTAP) or
`go/<product>/<deployment>/<use_case>/main.go` where the product has deployment
variants, and add a matching entry to [`catalog.yaml`](../catalog.yaml). See
[CONTRIBUTING.md](../CONTRIBUTING.md) and
[`docs/example-template/`](../docs/example-template/README.md).
