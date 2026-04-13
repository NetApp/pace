# Choosing an Automation Approach

This guide helps you pick the right tool for automating ONTAP workflows.
All four approaches in this repo do the same things — the difference is
**how much you write**, **what you control**, and **what the tool manages
for you**.

---

## Decision Flowchart

```mermaid
flowchart TD
    Start([What does your team need?]) --> Q1{Infrastructure lifecycle management?\n create / drift-detect / destroy}
    Q1 -->|Yes| Terraform[Terraform]
    Q1 -->|No| Q2{Fleet management across\nmultiple clusters?}
    Q2 -->|Yes| Ansible[Ansible]
    Q2 -->|No| Q3{Custom logic, branching,\nor Python integrations?}
    Q3 -->|Yes| Python[Python scripts]
    Q3 -->|No| Q4{Need the fastest path\nwith minimal code?}
    Q4 -->|Yes| YAML[YAML Workflows]
    Q4 -->|No| Any[Any approach works —\npick what your team knows]
```

Each tool has clear strengths. There is no single "right" answer — choose based
on your team's existing skills and the operational requirements of your workflow.

---

## Detailed Comparison

### Lines of code (real counts from this repo)

| Use case | YAML Workflows | Python | Ansible | Terraform |
|---|---|---|---|---|
| Cluster info | 41 | 54 (+188 shared client) | 63 | 72 |
| NFS provision | 118 | 145 (+188 shared client) | 96 | 155 |

Notes:
- Python scripts depend on a shared `ontap_client.py` (188 lines). The
  Orchestrio engine, Ansible collection, and Terraform provider provide
  this layer for you.
- YAML workflow line counts include `defaults:` blocks and comments.
- Terraform counts include `variables.tf` and `outputs.tf` boilerplate.

### Feature matrix

| Capability | Python | Ansible | Terraform | YAML Workflows |
|---|---|---|---|---|
| Idempotency | You build it | Yes (modules) | Yes (plan/apply) | No |
| State tracking | You build it | No (stateless runs) | Yes (.tfstate) | No |
| Drift detection | No | No | Yes (plan) | No |
| Destroy/rollback | You build it | Re-run with `state: absent` | `terraform destroy` | No |
| Retry on failure | You build it | `retries:` on tasks | Provider-level | Built-in (`retry:`) |
| Dry run / preview | No | `--check` (module-dependent) | `terraform plan` | `--dry-run` with template resolution |
| Interactive debug | Debugger (pdb) | `--step` (basic) | No | `--interactive` step-through |
| Structured logging | You build it | Callback plugins | JSON plan output | JSONL auto-logging |
| Step output chaining | Variables | `register` + Jinja2 | Resource references | `{{ steps.x.y }}` |
| Parallelism | Threading/asyncio | `serial`, `async` | Dependency graph | No (sequential) |
| Fleet / multi-target | Loops (you write) | Inventory groups | `for_each`, modules | No |
| Secret management | Env vars | Vault, external lookups | `sensitive`, backends | Env vars, `.env` files |
| Custom logic | Full language | Jinja2, filters | HCL expressions, functions | Shell steps, plugins |
| Ecosystem size | All of PyPI | 150+ ONTAP modules | Provider resources | 2 plugins (http, shell) |

### Setup effort

| | Python | Ansible | Terraform | YAML Workflows |
|---|---|---|---|---|
| **Install** | `pip install requests` | `pip install ansible` + `ansible-galaxy collection install netapp.ontap` | Download binary + `terraform init` | `pip install orchestrio` |
| **Config files needed** | 1 (script) + env | Inventory + group_vars + playbook | main.tf + variables.tf + tfvars | 1 (workflow YAML) |
| **Time to first run** | ~5 minutes | ~10 minutes | ~10 minutes | ~2 minutes |

---

## When Each Tool Shines

### Python scripts

- **Custom business logic** — if/else, loops, data transformation
- **Integration with other systems** — combine ONTAP calls with Slack, Jira, databases
- **One-off scripts** for teams that already think in Python
- **Full control** over error handling, retries, and output formatting

### Ansible playbooks

- **Fleet operations** — run the same playbook against 50 clusters via inventory
- **Idempotent provisioning** — `state: present` / `state: absent` does the right thing
- **Teams already using Ansible** for OS/app config management
- **Ansible Tower / AWX** — centralized scheduling, RBAC, audit trail

### Terraform

- **Infrastructure lifecycle** — create, update, destroy with full state tracking
- **Drift detection** — `terraform plan` shows what changed since last apply
- **Multi-provider** — manage ONTAP alongside AWS/Azure/GCP in one plan
- **Compliance / auditability** — state file is the source of truth

### YAML Workflows (Orchestrio)

- **Rapid prototyping** — quickest way to test an ONTAP REST API sequence
- **CI/CD pipeline steps** — single command, no server, deterministic output
- **API learning** — see exact REST calls (method, URL, headers, body)
- **Operational runbooks** — trigger backup, verify status, send notification
- **Interactive debugging** — step through a failing workflow one call at a time

---

## Migration Paths

As your automation needs grow, you may migrate between approaches:

```
                    ┌──→ Python      (need custom logic or integrations)
YAML Workflows ─────┼──→ Ansible     (need fleet management or idempotency)
                    └──→ Terraform   (need lifecycle management or multi-provider)

Python ─────────────┬──→ Ansible     (need inventory-driven fleet ops)
                    └──→ Terraform   (need state tracking and drift detection)
```

The YAML workflows serve as living documentation of the REST API sequence
regardless of which tool you ultimately use. The API endpoints, request
bodies, and response paths translate directly across all approaches.

---

## Quick Reference

| I want to... | Use |
|---|---|
| Get a workflow running in 2 minutes | YAML Workflows |
| See the exact REST API calls being made | YAML Workflows or Python |
| Step through a workflow interactively | YAML Workflows |
| Create resources that I can later destroy cleanly | Terraform |
| See what changed on my cluster since last run | Terraform |
| Run the same automation across many clusters | Ansible |
| Ensure repeated runs don't create duplicates | Ansible or Terraform |
| Add custom Python logic to a workflow | Python scripts |
| Integrate ONTAP automation with other tools | Python scripts |
| Combine ONTAP + cloud infra in one config | Terraform |
