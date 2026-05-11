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

Pace is an open-source library of ready-to-run **NetApp ONTAP** automation
examples, implemented three ways - side by side - so you can pick the
style your team already uses.

| Style                     | Tool      | In a sentence                       |
| ------------------------- | --------- | ----------------------------------- |
| **Imperative scripts**    | Python    | You write each step yourself.       |
| **Declarative playbooks** | Ansible   | You describe the outcome.           |
| **Stateful blueprints**   | Terraform | The tool tracks every change.       |

Same task, same outcome - different trade-offs in readability, idempotency,
and lifecycle management.

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
| [Project website](https://netapp.github.io/pace/)                     | Guided tour, prompts, full contribution guide  |
| [Choosing an approach](docs/choosing-an-approach.md)                  | Decision guide and feature matrix              |
| [ONTAP API patterns](docs/ontap-api-patterns.md)                      | REST conventions, auth, async jobs             |
| [Troubleshooting](docs/troubleshooting.md)                            | Common errors and fixes                        |
| [Testing](TESTING.md)                                                 | What to run and capture in the PR Test Report  |
| [Contributing](CONTRIBUTING.md)                                       | Fork, branch, run checks, open a PR            |

---

## License

[Apache-2.0](LICENSE) © NetApp

<div align="center">
  <sub><strong><a href="https://netapp.github.io/pace/">→ Explore the full project at netapp.github.io/pace</a></strong></sub>
</div>
