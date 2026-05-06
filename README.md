# Pace — Storage automation, in three different styles.

[![Website](https://img.shields.io/badge/Website-netapp.github.io%2Fpace-0067C5?style=for-the-badge&logo=readthedocs&logoColor=white)](https://netapp.github.io/pace/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

> **Full documentation, live examples, and the project home live at →
> [netapp.github.io/pace](https://netapp.github.io/pace/)**

Pace is an open-source library of ready-to-run **NetApp ONTAP** automation
examples written in three styles, side by side:

- **Imperative scripts** — Python: you write each step yourself.
- **Declarative playbooks** — Ansible: describe the outcome, not the steps.
- **Stateful blueprints** — Terraform: track every change, full lifecycle.

Same task, same outcome, different trade-offs. Pick the style your team
already uses and copy a working example in minutes.

---

## Quick Start

| Style | Directory | Run it |
|---|---|---|
| Imperative scripts | [`python/`](python/) | `cd python && pip install -r requirements.txt && python cluster_info.py` |
| Declarative playbooks | [`ansible/`](ansible/) | `cd ansible && ansible-playbook -i inventory/hosts.yml cluster_info.yml` |
| Stateful blueprints | [`terraform/`](terraform/) | `cd terraform/cluster-info && terraform init && terraform apply` |

> Host names, credentials, and resource names in every example are
> **placeholders**. Replace them with values from your environment before
> running. Each tool directory has its own README with full setup steps.

---

## Documentation

- **Project home:** [netapp.github.io/pace](https://netapp.github.io/pace/)
- [Choosing an approach](docs/choosing-an-approach.md) — decision guide and feature matrix
- [ONTAP API patterns](docs/ontap-api-patterns.md) — REST conventions, auth, async jobs
- [Troubleshooting](docs/troubleshooting.md) — common errors and fixes
- [Contributing](CONTRIBUTING.md) — fork, branch, run checks, open a PR

---

## Prerequisites

- An ONTAP cluster reachable over HTTPS (9.8+ recommended)
- Admin credentials (or a user with appropriate RBAC permissions)
- Network access to the cluster management LIF

Credentials are **never hardcoded** — each style uses its native secret
mechanism (env vars, Ansible Vault, Terraform `sensitive` variables).

SSL verification is **disabled by default** for self-signed certificates.
Enable it via `ONTAP_VERIFY_SSL=true` (Python), `ontap_validate_certs: true`
(Ansible), or `validate_certs = true` (Terraform).

---

## License

Apache-2.0 — see [LICENSE](LICENSE).

---

<p align="center">
  <a href="https://netapp.github.io/pace/">
    <strong>→ Visit the Pace website for the full guided tour</strong>
  </a>
</p>
