# Automation Examples — Choose Your Approach

This directory contains equivalent ONTAP automation examples implemented in
**Python**, **Ansible**, and **Terraform**. Each example mirrors a workflow
already available as low-code YAML in the parent repo's
[`workflows/`](../workflows/) directory, so you can compare approaches
side-by-side and pick the one that fits your team.

> **Orchestrio's low-code YAML workflows are the recommended starting point.**
> The examples here show the traditional scripting equivalent — useful for teams
> that already have investment in a specific toolchain or need capabilities
> beyond what declarative YAML provides.

---

## At a Glance

| | Orchestrio (YAML) | Python Script | Ansible Playbook | Terraform |
|---|---|---|---|---|
| **Lines of code** (cluster info) | ~15 | ~70 | ~40 | ~30 |
| **Install** | `pip install orchestrio` | `pip install requests` | `pip install ansible` + Galaxy collection | `terraform` binary + provider |
| **Learning curve** | YAML only | Python fluency | Ansible + ONTAP modules | HCL + provider knowledge |
| **State management** | Stateless (run-to-completion) | You manage it | Idempotent modules | Full state tracking |
| **Best for** | Rapid automation, CI/CD pipelines | Custom logic, complex branching | Config management teams, fleet ops | Infrastructure-as-code teams |
| **Error handling** | Built-in retry + on_failure | Try/except (you write it) | Module-level + rescue blocks | Plan/apply cycle |

---

## When to Use What

### Orchestrio YAML — start here

Use Orchestrio when you want to automate ONTAP REST API workflows with
**minimal code**. Write a YAML file, run `orchestrio run`, done. Best when:

- You want to go from zero to working automation in minutes
- The workflow is a linear sequence of REST calls (GET/POST/PATCH/DELETE)
- You need built-in retry, dry-run, and interactive step-through
- You want CI/CD-friendly automation without writing glue code

```yaml
# workflows/cluster_info.yaml — 15 lines, zero code
name: cluster_info
version: "1"
env:
  ONTAP_HOST: ""
  ONTAP_USER: "admin"
  ONTAP_PASS: ""
defaults:
  http:
    username: "{{ env.ONTAP_USER }}"
    password: "{{ env.ONTAP_PASS }}"
    verify_ssl: false
steps:
  - include: ../steps/ontap_get_cluster.yaml
  - include: ../steps/ontap_get_nodes.yaml
```

```bash
orchestrio run workflows/cluster_info.yaml -E cluster.env
```

### Python scripts — when you need full control

Use plain Python when your workflow has **complex conditional logic**,
**data transformations**, or **integrations** beyond REST calls. Best when:

- You need branching, loops, or dynamic decision-making
- You are integrating with other Python libraries or internal tools
- Your team already has Python expertise and existing code to build on

See: [python/](python/)

### Ansible playbooks — when you manage fleets

Use Ansible when you are already running Ansible for **configuration management**
across hosts and want ONTAP automation to fit into that workflow. Best when:

- You manage multiple clusters and need inventory-driven automation
- You want idempotent operations (run the same playbook repeatedly, safely)
- Your team already uses Ansible Tower / AWX for orchestration

See: [ansible/](ansible/) *(coming soon)*

### Terraform — when infrastructure is code

Use Terraform when you treat storage resources as **declarative infrastructure**
and want plan/apply lifecycle management. Best when:

- You manage ONTAP resources alongside cloud infrastructure (VPCs, VMs, etc.)
- You need drift detection and state management
- Your team already uses Terraform for infrastructure provisioning

See: [terraform/](terraform/) *(coming soon)*

---

## Workflow Coverage

Each approach implements the same use cases for direct comparison:

| Use Case | Orchestrio YAML | Python | Ansible | Terraform |
|---|---|---|---|---|
| **Cluster info** — retrieve cluster version and node list | [`workflows/cluster_info.yaml`](../workflows/cluster_info.yaml) | [`cluster_info.py`](python/cluster_info.py) | *coming soon* | *coming soon* |
| **NFS provision** — create volume, export policy, assign policy | [`workflows/nfs_provision.yaml`](../workflows/nfs_provision.yaml) | [`nfs_provision.py`](python/nfs_provision.py) | *coming soon* | *coming soon* |

---

## Prerequisites

All examples assume:

- An ONTAP cluster reachable over HTTPS (9.8+ recommended for full REST API support)
- Admin credentials (or a user with appropriate RBAC permissions)
- Network access from the machine running the automation to the cluster management LIF

Credentials are **never hardcoded** in any example. Each approach uses its
native mechanism for secrets: environment variables, `.env` files, Ansible Vault,
or Terraform variables marked `sensitive`.

---

## Repository Structure

```
automation-examples/
├── README.md              ← you are here
├── python/                ← Python script equivalents
│   ├── README.md
│   ├── requirements.txt
│   ├── ontap_client.py
│   ├── cluster_info.py
│   └── nfs_provision.py
├── ansible/               ← Ansible playbook equivalents
│   ├── README.md
│   ├── requirements.yml
│   ├── inventory/
│   ├── group_vars/
│   ├── cluster_info.yml
│   └── nfs_provision.yml
└── terraform/             ← Terraform config equivalents
    ├── README.md
    ├── cluster-info/
    └── nfs-provision/
```
