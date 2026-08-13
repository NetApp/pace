# Terraform — NetApp Console (local)

Placeholder for Terraform modules that automate NetApp Console in a `local`
deployment. **No modules live here yet** — this directory reserves the layout so
the first contribution has an obvious home.

## Adding the first module

1. Add `<use-case>/` (kebab-case) in this directory with `main.tf`,
   `variables.tf`, `outputs.tf`, and `terraform.tfvars.example`, following
   [`terraform/ontap/README.md`](../../ontap/README.md) and the skeleton in
   [`docs/example-template/terraform/`](../../../docs/example-template/README.md).
2. Keep it a self-contained root module with its own provider block and state.
3. Add a `use_cases` entry to [`catalog.yaml`](../../../catalog.yaml) with
   `product: console` and `deployment: local`. The variant `path` and `cwd` must
   both be `terraform/console/local/<use-case>`; see
   [`docs/catalog-spec.md`](../../../docs/catalog-spec.md).
4. Replace this file with a real README documenting inputs and outputs per
   module, matching the ONTAP README format.

CI discovers modules by looking for directories containing `*.tf`, so this empty
placeholder is skipped and a new module here is validated automatically.
