# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Product-scoped directory layout: examples now live under `<tool>/<product>/`,
  with placeholder `<tool>/console/local/` directories for NetApp Console
- Publication-ready Console (local) prompt catalog
  (`docs/console-local-prompt-catalog.md`, sourced from
  `ai/console/local/prompt-catalog.md`)
- `product` field in `catalog.yaml` (and optional `deployment`), enforced by
  `scripts/validate_catalog.py` to agree with each variant's path
- `ontap` and `console` PR labels
- `ai/` source tree as the single place to author AI instructions and prompts,
  with `scripts/generate_ai_assets.py` rendering the Copilot and Cursor formats
  (`make ai-assets`); CI fails when a generated copy drifts from its source
- Cursor support for the prompt library: `.cursor/commands/` slash commands and
  `.cursor/rules/` product rules, previously Copilot-only
- `AGENTS.md` — repo-wide agent instructions, read by Cursor and most other agents
- GitHub Copilot extension recommendations in `.vscode/extensions.json`, so the
  prompt library is offered on first open
- Dependency review on PRs, failing on high-severity advisories and copyleft licenses
- `requirements-dev.txt` pinning the lint toolchain, used by both CI and
  `make install`, with a Dependabot entry to keep the pins current
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
  `.github/copilot-instructions.md`, `.cursor/`, `AGENTS.md`, or
  `docs/ai-prompt-catalog.md` directly.
- `docs/ai-prompt-catalog.md` is now a generated index and 60% shorter. The
  hand-condensed copies of each prompt are gone — they duplicated the real
  prompts and drifted from them; the table links to the prompt sources instead.
  It is also linked from the README, CONTRIBUTING, and the website, having
  previously been orphaned.
- Each tool root README is now a short product index; the ONTAP documentation
  lives in `<tool>/ontap/README.md`
- CI discovers examples recursively instead of with fixed-depth globs, and fails
  when discovery finds nothing
- Reconciled TruffleHog versions between pre-commit and CI (both now `v3.94.2`)
- CHANGELOG restructured with granular categories

### Fixed

- TruffleHog flag mismatch: pre-commit used `--fail` but CI did not - both now use `--only-verified --fail`
- CI installed `ruff` unpinned, so ruff 0.16 widening its default rule set turned
  `main` red with no change to the repo. `ruff.toml` now states its rule selection
  explicitly and the toolchain is pinned, so the rule set changes only when
  someone decides to change it.
- Go changes did not trigger the Test Report soft gate, even though `TESTING.md`
  and the PR template both required a report for them. Go-only PRs could merge
  without the attestation the docs promised.
- `cache-dependency-path: go/go.sum` pointed at a file that does not exist (the
  examples are standard-library only), so `setup-go` silently skipped caching in
  both `ci.yml` and `validate-examples.yml`. Now keyed on `go/go.mod`.
- The copyright-header check globbed `poc/*.html`, which is gitignored and
  therefore never matched anything.
- `ansible` and `ansible-lint` were installed unpinned in `validate-examples.yml`,
  carrying the same risk as the ruff break.

[Unreleased]: https://github.com/NetApp/pace/commits/main
