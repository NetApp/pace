# Choosing an Automation Approach

This guide helps you pick the right tool for automating NetApp storage
workflows. All four approaches in this repo do the same things - the
difference is **how much you write**, **what you control**, and **what the
tool manages for you**.

---

## Decision Flowchart

```mermaid
flowchart TD
    Start([What does your team need?]) --> Q1{Infrastructure lifecycle management?\n create / drift-detect / destroy}
    Q1 -->|Yes| Terraform[Terraform]
    Q1 -->|No| Q2{Fleet management across\nmultiple clusters?}
    Q2 -->|Yes| Ansible[Ansible]
    Q2 -->|No| Q3{Strongly typed, single binary,\nor Go integrations?}
    Q3 -->|Yes| Go[Go]
    Q3 -->|No| Q4{Custom logic, branching,\nor Python integrations?}
    Q4 -->|Yes| Python[Python scripts]
    Q4 -->|No| Any[Any approach works -\npick what your team knows]
```

Each tool has clear strengths. There is no single "right" answer - choose based
on your team's existing skills and the operational requirements of your workflow.

---

## Detailed Comparison

### Lines of code (real counts from this repo)

| Use case | Python | Ansible | Terraform | Go |
|---|---|---|---|---|
| Cluster info | 54 (+188 shared client) | 63 | 72 | ~70 (+shared client) |
| NFS provision | 145 (+188 shared client) | 96 | 155 | ~160 (+shared client) |
| CIFS provision | 200 (+188 shared client) | 120 | 180 | ~220 (+shared client) |
| Cluster setup | 95 (+188 shared client) | 80 | — | ~240 (+shared client) |

Notes:
- Python and Go scripts depend on a shared client, one per product
  (`python/ontap/ontap_client.py` / `go/ontap/ontapclient`).
  The Ansible collection and Terraform provider provide this layer for you.
- Terraform counts include `variables.tf` and `outputs.tf` boilerplate.

### Feature matrix

| Capability | Python | Ansible | Terraform | Go |
|---|---|---|---|---|
| Idempotency | You build it | Yes (modules) | Yes (plan/apply) | You build it |
| State tracking | You build it | No (stateless runs) | Yes (.tfstate) | You build it |
| Drift detection | No | No | Yes (plan) | No |
| Destroy/rollback | You build it | Re-run with `state: absent` | `terraform destroy` | You build it |
| Retry on failure | You build it | `retries:` on tasks | Provider-level | You build it |
| Dry run / preview | No | `--check` (module-dependent) | `terraform plan` | No |
| Interactive debug | Debugger (pdb) | `--step` (basic) | No | Debugger (dlv) |
| Structured logging | You build it | Callback plugins | JSON plan output | You build it |
| Step output chaining | Variables | `register` + Jinja2 | Resource references | Variables |
| Parallelism | Threading/asyncio | `serial`, `async` | Dependency graph | Goroutines |
| Fleet / multi-target | Loops (you write) | Inventory groups | `for_each`, modules | Loops (you write) |
| Secret management | Env vars | Vault, external lookups | `sensitive`, backends | Env vars |
| Custom logic | Full language | Jinja2, filters | HCL expressions, functions | Full language |
| Ecosystem size | All of PyPI | 150+ ONTAP modules | Provider resources | All of Go modules |
| Compiled binary | No | No | Yes (provider) | Yes |

### Setup effort

| | Python | Ansible | Terraform | Go |
|---|---|---|---|---|
| **Install** | `pip install requests` | `pip install ansible` + `ansible-galaxy collection install netapp.ontap` | Download binary + `terraform init` | `go mod download` |
| **Config files needed** | 1 (script) + env | Inventory + group_vars + playbook | main.tf + variables.tf + tfvars | 1 (main.go) + env |
| **Time to first run** | ~5 minutes | ~10 minutes | ~10 minutes | ~5 minutes |

---

## When Each Tool Shines

### Python scripts

- **Custom business logic** - if/else, loops, data transformation
- **Integration with other systems** - combine storage calls with Slack, Jira, databases
- **One-off scripts** for teams that already think in Python
- **Full control** over error handling, retries, and output formatting

### Ansible playbooks

- **Fleet operations** - run the same playbook against 50 clusters via inventory
- **Idempotent provisioning** - `state: present` / `state: absent` does the right thing
- **Teams already using Ansible** for OS/app config management
- **Ansible Tower / AWX** - centralized scheduling, RBAC, audit trail

### Terraform

- **Infrastructure lifecycle** - create, update, destroy with full state tracking
- **Drift detection** - `terraform plan` shows what changed since last apply
- **Multi-provider** - manage NetApp storage alongside AWS/Azure/GCP in one plan
- **Compliance / auditability** - state file is the source of truth

### Go programs

- **Type safety** - compile-time checks catch API field mismatches early
- **Single compiled binary** - distribute one executable, no runtime deps
- **Go integrations** - combine storage calls with Go services, CLIs, or gRPC
- **Performance** - goroutines for concurrent multi-cluster operations
- **Teams already using Go** for infrastructure tooling or CLIs

---

## Migration Paths

As your automation needs grow, you may migrate between approaches:

```
Python ─────────────┬──→ Ansible     (need inventory-driven fleet ops)
                    ├──→ Terraform   (need state tracking and drift detection)
                    └──→ Go          (need compiled binary or Go integrations)
```

The API endpoints, request bodies, and response paths translate directly
across all approaches.

---

## Quick Reference

| I want to... | Use |
|---|---|
| See the exact REST API calls being made | Python or Go |
| Create resources that I can later destroy cleanly | Terraform |
| See what changed on my cluster since last run | Terraform |
| Run the same automation across many clusters | Ansible |
| Ensure repeated runs don't create duplicates | Ansible or Terraform |
| Add custom Python logic to a workflow | Python scripts |
| Compile a single distributable binary | Go |
| Integrate storage automation with other tools | Python scripts or Go |
| Combine NetApp storage + cloud infra in one config | Terraform |
