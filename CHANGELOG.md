# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Product-scoped directory layout: examples now live under `<tool>/<product>/`,
  with placeholder `<tool>/console/local/` directories for NetApp Console
- `product` field in `catalog.yaml` (and optional `deployment`), enforced by
  `scripts/validate_catalog.py` to agree with each variant's path
- `ontap` and `console` PR labels
- `ai/` source tree as the single place to author AI instructions and prompts,
  with `scripts/generate_ai_assets.py` rendering the Copilot and Cursor formats
  (`make ai-assets`); CI fails when a generated copy drifts from its source
- Cursor support for the prompt library: `.cursor/commands/` slash commands and
  `.cursor/rules/` product rules, previously Copilot-only
- `AGENTS.md` — repo-wide agent instructions, read by Cursor and most other agents
- Product-scoped AI conventions attached automatically by path
  (`.github/instructions/`, `.cursor/rules/`) for `ontap` and `console/local`
- Initial NetApp storage automation examples for Python, Ansible, Terraform, and Go
- CI workflows for linting, syntax validation, and secret scanning
- Platform API patterns documentation
- Dockerfile and docker-compose.yml for reproducible dev environment
- Dependabot configuration for GitHub Actions, pip, and Terraform
- Troubleshooting guide (`docs/troubleshooting.md`)
- Documentation: default-values warning, no-tests disclaimer, idempotency guidance

### Changed

- **Breaking (paths):** every example moved from the tool root into an `ontap/`
  product directory — e.g. `python/cluster_info.py` is now
  `python/ontap/cluster_info.py` and `terraform/nfs-provision/` is now
  `terraform/ontap/nfs-provision/`. Local scripts, bookmarks, and `cd` commands
  need updating; run commands themselves are unchanged once you are in the new
  directory.
- **Breaking (Go import):** the shared client package moved to
  `github.com/netapp/pace/go/ontap/ontapclient`. The module path
  (`github.com/netapp/pace/go`) is unchanged.
- **Breaking (prompt names):** prompts are now product-scoped, so
  `/generate-python` is `/ontap-generate-python` (likewise `-ansible`,
  `-terraform`, `-go`, `-workflow`, and `/plan-api-sequence` →
  `/ontap-plan-api-sequence`). `/review-contribution` is unchanged because it
  applies to every product.
- Prompt and instruction files are generated. Edit the source under `ai/` and
  run `make ai-assets`; do not edit `.github/prompts/`,
  `.github/copilot-instructions.md`, `.cursor/`, or `AGENTS.md` directly.
- Each tool root README is now a short product index; the ONTAP documentation
  lives in `<tool>/ontap/README.md`
- CI discovers examples recursively instead of with fixed-depth globs, and fails
  when discovery finds nothing
- Reconciled TruffleHog versions between pre-commit and CI (both now `v3.94.2`)
- CHANGELOG restructured with granular categories

### Fixed

- TruffleHog flag mismatch: pre-commit used `--fail` but CI did not - both now use `--only-verified --fail`

[Unreleased]: https://github.com/NetApp/pace/commits/main
