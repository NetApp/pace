# Go — NetApp Console (local)

Placeholder for Go programs that automate NetApp Console in a `local`
deployment. **No programs live here yet** — this directory reserves the layout so
the first contribution has an obvious home.

## Adding the first program

1. Add `<use_case>/main.go` in this directory, following the conventions in
   [`go/ontap/README.md`](../../ontap/README.md) and the skeleton in
   [`docs/example-template/go/example.go`](../../../docs/example-template/go/example.go).
2. Add a `consoleclient/` package here — the shared REST client is per product.
   Programs import it as
   `github.com/netapp/pace/go/console/local/consoleclient`. The Go module stays
   rooted at `go/`, so run `go mod download` from `go/`.
3. Add a `use_cases` entry to [`catalog.yaml`](../../../catalog.yaml) with
   `product: console` and `deployment: local`. The variant `path` must be
   `go/console/local/<use_case>/main.go` and `cwd` must be
   `go/console/local/<use_case>`; see
   [`docs/catalog-spec.md`](../../../docs/catalog-spec.md).
4. Replace this file with a real README documenting env vars and outputs per
   program, matching the ONTAP README format.

CI discovers programs by looking for `main.go` recursively under `go/`, so a new
program here is vetted and build-checked automatically.
