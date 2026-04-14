# Orchestrio Support and Getting Help

Orchestrio is an open-source project developed and published by NetApp providing
production-ready automation examples for ONTAP, implemented in Python, Ansible,
and Terraform. Orchestrio is not an officially supported NetApp product. NetApp
maintains and updates Orchestrio with bug fixes, security updates, and feature
development. For assistance, refer to [Getting Help](#getting-help).

## Release and Support Lifecycle

Orchestrio follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Each release is tagged as `vMAJOR.MINOR.PATCH` and published on GitHub Releases.

All examples target ONTAP 9.8+ REST APIs. When breaking changes are required,
they will be outlined in the [CHANGELOG](CHANGELOG.md).

We recommend always running the latest version.

## Getting Help

We use GitHub for tracking bugs and feature requests.

- **Bug reports** — [open an issue](https://github.com/NetApp/orchestrio/issues/new?template=bug_report.md)
- **Feature requests** — [open an issue](https://github.com/NetApp/orchestrio/issues/new?template=feature_request.md)
- **Questions and discussion** — [GitHub Discussions](https://github.com/NetApp/orchestrio/discussions)

## Documentation

* [README](README.md) — project overview and quick start
* [Contributing](CONTRIBUTING.md) — how to add examples and what CI expects
* [ONTAP API Patterns](docs/ontap-api-patterns.md) — REST endpoint conventions
* [Orchestrio Workflows](docs/orchestrio.md) — YAML workflow authoring guide
