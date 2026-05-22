# Pace Support and Getting Help

Pace is an open-source project developed and published by NetApp providing
NetApp storage automation examples, implemented in Python, Ansible, and Terraform.
Pace is not an officially supported NetApp product. NetApp
maintains and updates Pace with bug fixes, security updates, and feature
development. For assistance, refer to [Getting Help](#getting-help).

## Release and Support Lifecycle

Pace follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Each release is tagged as `vMAJOR.MINOR.PATCH` and published on GitHub Releases.

All examples target ONTAP 9.8+ REST APIs. When breaking changes are required,
they will be outlined in the [CHANGELOG](CHANGELOG.md).

We recommend always running the latest version.

## Getting Help

We use GitHub for tracking bugs and feature requests.

- **Bug reports** - [open an issue](https://github.com/NetApp/pace/issues/new?template=bug_report.yml)
- **Feature requests** - [open an issue](https://github.com/NetApp/pace/issues/new?template=feature_request.yml)
- **Questions and discussion** - [GitHub Discussions](https://github.com/NetApp/pace/discussions)
- **Private contact** - <ng-pace@netapp.com> (for security disclosures,
  conduct concerns, or anything else that should not be discussed in
  public. For everyday questions, please use Discussions instead - the
  team will respond faster and the answer benefits the next person.)

## Documentation

* [README](README.md) - project overview and quick start
* [Contributing](CONTRIBUTING.md) - how to add examples and what CI expects
* [Platform API Patterns](docs/ontap-api-patterns.md) - REST endpoint conventions
* [Troubleshooting](docs/troubleshooting.md) - common errors and how to fix them
