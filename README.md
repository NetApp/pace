<div align="center">

# Pace

### Storage automation, in three different styles

[![Website](https://img.shields.io/badge/Website-netapp.github.io%2Fpace-0067C5?style=for-the-badge&logo=readthedocs&logoColor=white)](https://netapp.github.io/pace/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg?style=for-the-badge)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)

**[Website](https://netapp.github.io/pace/)** ·
**[Choosing an approach](docs/choosing-an-approach.md)** ·
**[Contributing](CONTRIBUTING.md)** ·
**[Troubleshooting](docs/troubleshooting.md)**

</div>

---

> **New here? Pick the path that matches you.**
>
> | You are… | Start with |
> |---|---|
> | Just trying out an example | [Quick start](#quick-start) below — copy, paste, run. |
> | First-time contributor | [CONTRIBUTING.md](CONTRIBUTING.md) — `make install && make hooks` gets you set up in a couple of minutes. |
> | New to NetApp ONTAP | [Troubleshooting guide](docs/troubleshooting.md) plus the per-style READMEs in [`python/`](python/), [`ansible/`](ansible/), [`terraform/`](terraform/). |
> | Stuck or have a question | Open a [Discussion](https://github.com/NetApp/pace/discussions) — faster than a GitHub issue for questions. |

---

Pace is an open-source library of ready-to-run **NetApp storage automation**
examples, implemented three ways - side by side - so you can pick the
style your team already uses.

| Style                     | Tool      | In a sentence                       |
| ------------------------- | --------- | ----------------------------------- |
| **Imperative scripts**    | Python    | You write each step yourself.       |
| **Declarative playbooks** | Ansible   | You describe the outcome.           |
| **Stateful blueprints**   | Terraform | The tool tracks every change.       |

Same task, same outcome - different trade-offs in readability, idempotency,
and lifecycle management.

The examples in this repository target NetApp ONTAP - see
[Prerequisites](#prerequisites) for the exact requirements.

Every example is indexed in [`catalog.yaml`](catalog.yaml) (machine-readable)
with prerequisites, run commands, and inputs/outputs. Human-readable sections
live in the per-style READMEs linked below.

> Visit **[netapp.github.io/pace](https://netapp.github.io/pace/)** for the
> full guided tour, live code examples, and side-by-side comparisons.

---

## Quick start

Pick a style and run the matching block. All examples use placeholder host
names and credentials - swap them for your own before running.

<details open>
<summary><strong>Imperative scripts - Python</strong></summary>

```bash
cd python
pip install -r requirements.txt
export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=changeme
python cluster_info.py
```

</details>

<details>
<summary><strong>Declarative playbooks - Ansible</strong></summary>

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp group_vars/ontap.yml.example group_vars/ontap.yml   # edit with your details
ansible-playbook -i inventory/hosts.yml cluster_info.yml
```

</details>

<details>
<summary><strong>Stateful blueprints - Terraform</strong></summary>

```bash
cd terraform/cluster-info
cp terraform.tfvars.example terraform.tfvars          # edit with your details
terraform init && terraform apply
```

</details>

Each style directory has its own README with full setup steps, options,
and example output.

| Use case | Python | Ansible | Terraform |
| -------- | ------ | ------- | --------- |
| Cluster info | [python/](python/README.md#cluster-info) | [ansible/](ansible/README.md#cluster-info) | [terraform/](terraform/README.md#cluster-info) |
| NFS provision | [python/](python/README.md#nfs-volume-provisioning) | [ansible/](ansible/README.md#nfs-volume-provisioning) | [terraform/](terraform/README.md#nfs-volume-provisioning) |
| CIFS provision | [python/](python/README.md#cifs-share-provisioning) | [ansible/](ansible/README.md#cifs-share-provisioning) | [terraform/](terraform/README.md#cifs-smb-share-provisioning) |
| Cluster setup | [python/](python/README.md#cluster-setup) | [ansible/](ansible/README.md#cluster-setup) | — |
| SnapMirror provision (source) | [python/](python/README.md#snapmirror-provision-source-managed) | [ansible/](ansible/README.md#snapmirror-provision-source-managed) | — |
| SnapMirror provision (dest) | [python/](python/README.md#snapmirror-provision-destination-managed) | [ansible/](ansible/README.md#snapmirror-provision-destination-managed) | — |
| SnapMirror test failover | [python/](python/README.md#snapmirror-test-failover) | [ansible/](ansible/README.md#snapmirror-test-failover) | — |
| SnapMirror cleanup failover | [python/](python/README.md#snapmirror-cleanup-test-failover) | [ansible/](ansible/README.md#snapmirror-cleanup-test-failover) | — |

---

## Prerequisites

- ONTAP cluster reachable over HTTPS (9.8+ recommended)
- Admin credentials, or a user with appropriate RBAC permissions
- Network access to the cluster management LIF

Credentials are never hardcoded. Each style uses its native secret
mechanism - environment variables, Ansible Vault, or Terraform `sensitive`
variables.

<details>
<summary><strong>SSL verification</strong> is disabled by default for self-signed certificates</summary>

| Style     | Enable verification                                      |
| --------- | -------------------------------------------------------- |
| Python    | `export ONTAP_VERIFY_SSL=true`                           |
| Ansible   | `ontap_validate_certs: true` in `group_vars/ontap.yml`   |
| Terraform | `validate_certs = true` in `terraform.tfvars`            |

Once CA-signed certificates are in place, we recommend turning it on.

</details>

---

## Documentation

| Link                                                                  | What's inside                                  |
| --------------------------------------------------------------------- | ---------------------------------------------- |
| [Example catalog](catalog.yaml)                                       | Machine-readable index of all use cases        |
| [Catalog spec](docs/catalog-spec.md)                                  | Field definitions for `catalog.yaml`           |
| [Project website](https://netapp.github.io/pace/)                     | Guided tour, prompts, full contribution guide  |
| [Choosing an approach](docs/choosing-an-approach.md)                  | Decision guide and feature matrix              |
| [Platform API patterns](docs/ontap-api-patterns.md)                   | REST conventions, auth, async jobs             |
| [Troubleshooting](docs/troubleshooting.md)                            | Common errors and fixes                        |
| [Testing](TESTING.md)                                                 | What to run and capture in the PR Test Report  |
| [Contributing](CONTRIBUTING.md)                                       | Fork, branch, run checks, open a PR            |

---

## License

[Apache-2.0](LICENSE) © NetApp

<div align="center">
  <sub><strong><a href="https://netapp.github.io/pace/">→ Explore the full project at netapp.github.io/pace</a></strong></sub>
</div>
