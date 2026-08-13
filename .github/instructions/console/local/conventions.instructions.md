---
applyTo: "**/console/local/**"
---
<!-- Generated from ai/console/local/conventions.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# NetApp Console (local) conventions

There are no Console examples yet. `<tool>/console/local/` directories exist as
placeholders so the layout is ready when the first one arrives.

Only the structural conventions are settled so far:

- Examples live under `python/console/local/`, `ansible/console/local/`,
  `terraform/console/local/`, or `go/console/local/` - never at the tool root
  and never directly under `console/`.
- The `console` product requires a deployment level. `local` is the only
  supported value today; see [docs/catalog-spec.md](../../../../docs/catalog-spec.md).
- Every example needs a `catalog.yaml` entry with `product: console` and
  `deployment: local`, validated by
  [scripts/validate_catalog.py](../../../../scripts/validate_catalog.py).
- The repo-wide rules still apply: copyright headers, no hardcoded
  credentials, and a Test Report in the PR per [TESTING.md](../../../../TESTING.md).

**Do not assume ONTAP conventions carry over.** The API surface, auth model,
and client library for Console are not established in this repository yet.
When the first example lands, add the real conventions here and the
corresponding task prompts alongside this file.
