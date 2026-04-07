# Choosing an Automation Approach

This guide helps you pick the right tool for automating ONTAP workflows.
All four approaches in this repo do the same things — the difference is
**how much you write**, **what you control**, and **what the tool manages
for you**.

---

## Decision Flowchart

```
Start
  │
  ├─ Do you need infrastructure lifecycle management
  │  (create, track drift, update, destroy)?
  │     YES → Terraform
  │     NO ↓
  │
  ├─ Do you manage multiple clusters with inventory-driven
  │  automation, or already use Ansible?
  │     YES → Ansible
  │     NO ↓
  │
  ├─ Do you need complex branching, loops, or integration
  │  with Python libraries?
  │     YES → Python scripts
  │     NO ↓
  │
  └─ Orchestrio YAML — fastest path to a working workflow
```

---

## Detailed Comparison

### Lines of code (real counts from this repo)

| Use case | Orchestrio YAML | Python | Ansible | Terraform |
|---|---|---|---|---|
| Cluster info | 41 | 54 (+188 shared client) | 63 | 72 |
| NFS provision | 118 | 145 (+188 shared client) | 96 | 155 |

Notes:
- Python scripts depend on a shared `ontap_client.py` (188 lines). The
  Orchestrio engine, Ansible collection, and Terraform provider provide
  this layer for you.
- Orchestrio YAML line counts include `defaults:` blocks and comments.
  The executable step count is lower (4 steps for cluster info, 9 for
  NFS provision).
- Terraform counts include `variables.tf` and `outputs.tf` boilerplate.

### Feature matrix

| Capability | Orchestrio | Python | Ansible | Terraform |
|---|---|---|---|---|
| Idempotency | No | You build it | Yes (modules) | Yes (plan/apply) |
| State tracking | No | You build it | No (stateless runs) | Yes (.tfstate) |
| Drift detection | No | No | No | Yes (plan) |
| Destroy/rollback | No | You build it | Re-run with `state: absent` | `terraform destroy` |
| Retry on failure | Built-in (`retry:`) | You build it | `retries:` on tasks | Provider-level |
| Dry run / preview | `--dry-run` with template resolution | No | `--check` (module-dependent) | `terraform plan` |
| Interactive debug | `--interactive` step-through | Debugger (pdb) | `--step` (basic) | No |
| Structured logging | JSONL auto-logging | You build it | Callback plugins | JSON plan output |
| Step output chaining | `{{ steps.x.y }}` | Variables | `register` + Jinja2 | Resource references |
| Parallelism | No (sequential) | Threading/asyncio | `serial`, `async` | Dependency graph |
| Fleet / multi-target | No | Loops (you write) | Inventory groups | `for_each`, modules |
| Secret management | Env vars, `.env` files | Env vars | Vault, external lookups | `sensitive`, backends |
| Custom logic | Shell steps, plugins | Full language | Jinja2, filters | HCL expressions, functions |
| Ecosystem size | 2 plugins (http, shell) | All of PyPI | 150+ ONTAP modules | Provider resources |

### Setup effort

| | Orchestrio | Python | Ansible | Terraform |
|---|---|---|---|---|
| **Install** | `pip install orchestrio` | `pip install requests` | `pip install ansible` + `ansible-galaxy collection install netapp.ontap` | Download binary + `terraform init` |
| **Config files needed** | 1 (workflow YAML) | 1 (script) + env | Inventory + group_vars + playbook | main.tf + variables.tf + tfvars |
| **Time to first run** | ~2 minutes | ~5 minutes | ~10 minutes | ~10 minutes |

---

## When Each Tool Shines

### Orchestrio YAML

- **Rapid prototyping** — quickest way to test an ONTAP REST API sequence
- **CI/CD pipeline steps** — single command, no server, deterministic output
- **API learning** — see exact REST calls (method, URL, headers, body)
- **Operational runbooks** — trigger backup, verify status, send notification
- **Interactive debugging** — step through a failing workflow one call at a time

### Python scripts

- **Custom business logic** — if/else, loops, data transformation
- **Integration with other systems** — combine ONTAP calls with Slack, Jira, databases
- **One-off scripts** for teams that already think in Python
- **When you outgrow YAML** — start with Orchestrio, move to Python when you need more

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

---

## Migration Paths

As your automation needs grow, you may migrate between approaches:

```
Orchestrio YAML
  │
  ├──→ Python scripts    (need custom logic or integrations)
  ├──→ Ansible           (need fleet management or idempotency)
  └──→ Terraform         (need lifecycle management or multi-provider)
```

The YAML workflows serve as living documentation of the REST API sequence
regardless of which tool you ultimately use. The API endpoints, request
bodies, and response paths in the Orchestrio YAML translate directly to
the other approaches.

---

## Quick Reference

| I want to... | Use |
|---|---|
| Get a workflow running in 2 minutes | Orchestrio |
| See the exact REST API calls being made | Orchestrio |
| Step through a workflow interactively | Orchestrio |
| Create resources that I can later destroy cleanly | Terraform |
| See what changed on my cluster since last run | Terraform |
| Run the same automation across many clusters | Ansible |
| Ensure repeated runs don't create duplicates | Ansible or Terraform |
| Add custom Python logic to a workflow | Python scripts |
| Integrate ONTAP automation with other tools | Python scripts |
| Combine ONTAP + cloud infra in one config | Terraform |
