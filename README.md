# Orchestrio — ONTAP Automation Examples

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

Production-ready automation examples for NetApp ONTAP, implemented in **Python**,
**Ansible**, and **Terraform**. Pick the tool your team already uses and get a
working script in minutes.

---

## Pick Your Tool

| | Python | Ansible | Terraform | YAML Workflows |
|---|---|---|---|---|
| **Directory** | [`python/`](python/) | [`ansible/`](ansible/) | [`terraform/`](terraform/) | [`yaml-workflows/`](yaml-workflows/) |
| **Best for** | Custom logic, integrations | Fleet ops, config management | Infrastructure lifecycle | Rapid prototyping, CI/CD |
| **Install** | `pip install requests` | `pip install ansible` + Galaxy collection | `terraform` binary + provider | `git clone` + `pip install -e .` ([details](docs/orchestrio.md#install)) |
| **Learning curve** | Python fluency | Ansible + ONTAP modules | HCL + provider knowledge | YAML only |
| **State management** | You manage it | Idempotent modules | Full state tracking | Stateless |

Not sure which to choose? Read the [detailed comparison](docs/choosing-an-approach.md).

---

## Use Cases

Each use case is implemented across all approaches so you can compare side-by-side:

| Use Case | Python | Ansible | Terraform | YAML |
|---|---|---|---|---|
| **Cluster info** — version and node list | [cluster_info.py](python/cluster_info.py) | [cluster_info.yml](ansible/cluster_info.yml) | [cluster-info/](terraform/cluster-info/) | [cluster_info.yaml](yaml-workflows/workflows/cluster_info.yaml) |
| **NFS provision** — volume + export policy | [nfs_provision.py](python/nfs_provision.py) | [nfs_provision.yml](ansible/nfs_provision.yml) | [nfs-provision/](terraform/nfs-provision/) | [nfs_provision.yaml](yaml-workflows/workflows/nfs_provision.yaml) |

More use cases (CIFS, SnapMirror, snapshots, SVM) are on the roadmap.

---

## Quick Start

### Python

```bash
cd python
pip install -r requirements.txt
export ONTAP_HOST=10.0.0.1 ONTAP_USER=admin ONTAP_PASS=changeme
python cluster_info.py
```

### Ansible

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp group_vars/ontap.yml.example group_vars/ontap.yml
# edit group_vars/ontap.yml with your cluster details
ansible-playbook -i inventory/hosts.yml cluster_info.yml
```

### Terraform

```bash
cd terraform/cluster-info
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your cluster details
terraform init && terraform apply
```

### YAML Workflows (Orchestrio CLI)

```bash
cd yaml-workflows/executor
pip install -e .
cd ../..
orchestrio run yaml-workflows/workflows/cluster_info.yaml -E yaml-workflows/workflows/cluster_info.env
```

See the full [Orchestrio CLI documentation](docs/orchestrio.md) for install options,
workflow syntax, template reference, and plugin development.

---

## Prerequisites

All examples assume:

- An ONTAP cluster reachable over HTTPS (9.8+ recommended for full REST API support)
- Admin credentials (or a user with appropriate RBAC permissions)
- Network access from your machine to the cluster management LIF

Credentials are **never hardcoded**. Each approach uses its native secret mechanism:
environment variables, `.env` files, Ansible Vault, or Terraform `sensitive` variables.

For details on ONTAP REST API conventions (endpoints, auth, headers, async jobs),
see the [ONTAP API patterns guide](docs/ontap-api-patterns.md).

---

## Repository Structure

```
orchestrio/
├── python/                 # Python script examples
├── ansible/                # Ansible playbook examples
├── terraform/              # Terraform module examples
├── yaml-workflows/         # Declarative YAML workflow executor (Orchestrio CLI)
│   ├── executor/           #   Python CLI package
│   ├── workflows/          #   Runnable workflow files
│   ├── steps/              #   Reusable step fragments
│   ├── examples/           #   Tutorial workflows
│   └── workflow-spec/      #   JSON schema (v1)
├── docs/
│   ├── choosing-an-approach.md
│   ├── ontap-api-patterns.md
│   └── orchestrio.md
└── .github/                # CI workflows, templates, review config
```

---

## Documentation

| Document | Description |
|---|---|
| [Choosing an approach](docs/choosing-an-approach.md) | Decision guide and feature matrix across all four tools |
| [ONTAP API patterns](docs/ontap-api-patterns.md) | REST API conventions: endpoints, auth, headers, async jobs |
| [Orchestrio CLI](docs/orchestrio.md) | YAML workflow executor: install, concepts, CLI reference, plugins |

---

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
