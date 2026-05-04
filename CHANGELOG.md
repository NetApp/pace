# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial ONTAP automation examples for Python, Ansible, and Terraform
- CI workflows for linting, syntax validation, and secret scanning
- Documentation for ONTAP API patterns
- Dockerfile and docker-compose.yml for reproducible dev environment
- Dependabot configuration for GitHub Actions, pip, and Terraform
- Troubleshooting guide (`docs/troubleshooting.md`)
- Documentation: default-values warning, no-tests disclaimer, idempotency guidance

### Changed

- Reconciled TruffleHog versions between pre-commit and CI (both now `v3.94.2`)
- CHANGELOG restructured with granular categories

### Fixed

- TruffleHog flag mismatch: pre-commit used `--fail` but CI did not — both now use `--only-verified --fail`

[Unreleased]: https://github.com/NetApp/pace/commits/main
