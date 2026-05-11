# AI Prompt Catalog for ONTAP Workflow Generation

This repository ships **reusable AI prompts** in two forms:

1. **Copilot-native prompt files** in `.github/prompts/` - usable directly
   from GitHub Copilot Chat, VS Code Copilot, and Cursor.
2. **Copy-paste prompts** (below) - for any AI assistant (ChatGPT, Gemini,
   Claude, etc.).

---

## Using Copilot Prompt Files (Recommended)

The `.github/prompts/` directory contains `.prompt.md` files that Copilot
discovers automatically.

### In VS Code / Cursor (Copilot Chat)

1. Open Copilot Chat.
2. Type `/` and select the prompt from the picker, or type its name directly.
3. Replace `{task description}` with your storage task.
4. Copilot automatically has access to the referenced repository files.

### In GitHub.com (Copilot in PR / Issue)

The prompt files are part of the repo, so Copilot has repo-context when
generating suggestions in PRs and issues.

### Available Prompts

| Prompt File | Copilot Name | Use When |
|-------------|-------------|----------|
| `generate-python.prompt.md` | `generate-python` | You need a Python script only |
| `generate-ansible.prompt.md` | `generate-ansible` | You need an Ansible playbook only |
| `generate-terraform.prompt.md` | `generate-terraform` | You need a Terraform module only |
| `generate-workflow.prompt.md` | `generate-workflow` | You need all three implementations |
| `plan-api-sequence.prompt.md` | `plan-api-sequence` | Design the API call sequence before coding |
| `review-contribution.prompt.md` | `review-contribution` | Check code against conventions before a PR |

### Recommended Workflow

```
1.  plan-api-sequence       →  Design and validate the REST API sequence
2.  generate-workflow        →  Generate Python + Ansible + Terraform
    (or generate-python / generate-ansible / generate-terraform individually)
3.  review-contribution      →  Verify conventions, CI compliance, README updates
```

---

## Copy-Paste Prompts (Tool-Agnostic)

For AI assistants without Copilot prompt file support, copy the relevant
prompt below, paste it into the chat window, and replace the `[PLACEHOLDER]`
values.

---

### Python-Only Prompt

````text
You are a NetApp ONTAP automation engineer writing a Python script that uses
ONLY the ONTAP REST API.

Task: [DESCRIBE THE STORAGE TASK]

STEP 1 - CLARIFY: Ask me for any missing information (SVM, volume, aggregate,
protocol, cluster hostname, special options).

STEP 2 - API SEQUENCE: List ONTAP REST API calls in order. For each: method,
endpoint, key body/query params, sync/async, one-sentence justification.
Rules: REST only (no ZAPI, no CLI, no SSH), target ONTAP 9.8+. Wait for my
approval.

STEP 3 - GENERATE PYTHON: File `python/<use_case>.py` with:
  • #!/usr/bin/env python3, from __future__ import annotations
  • Module docstring with steps, prerequisites, usage
  • from ontap_client import OntapClient (shared client, do NOT create a new one)
  • with OntapClient.from_env() as client: (env: ONTAP_HOST, ONTAP_PASS)
  • argparse with env-var fallbacks for operational params
  • client.get/post/patch/delete + client.poll_job() for async
  • logging module only (no print), type hints, no hardcoded credentials
  • if __name__ == "__main__": try/except guard with sys.exit(1)

STEP 4 - VALIDATE: Run commands, error scenarios, teardown instructions.
````

---

### Ansible-Only Prompt

````text
You are a NetApp ONTAP automation engineer writing an Ansible playbook using
the netapp.ontap collection (REST API only).

Task: [DESCRIBE THE STORAGE TASK]

STEP 1 - CLARIFY: Ask for missing info (SVM, volume, aggregate, protocol,
cluster hostname, special options).

STEP 2 - API SEQUENCE: List REST calls and map each to a netapp.ontap module.
Rules: use_rest: always, ONTAP 9.8+, FQCNs (netapp.ontap.na_ontap_*).
Wait for approval.

STEP 3 - GENERATE PLAYBOOK: File `ansible/<use_case>.yml` with:
  • --- header comment with filename, description, usage
  • hosts: ontap, gather_facts: false, connection: local
  • vars: section for operational defaults (overridable with -e)
  • Every ONTAP task: hostname/username/password/https/validate_certs from
    variables, use_rest: always, no_log: false
  • state: present for creates, wait_for_completion: true where supported
  • Final ansible.builtin.debug summary. No hardcoded credentials.

STEP 4 - VALIDATE: Run command, idempotency behavior, teardown playbook.
````

---

### Terraform-Only Prompt

````text
You are a NetApp ONTAP automation engineer writing a Terraform module using
the NetApp/netapp-ontap provider (REST API only).

Task: [DESCRIBE THE STORAGE TASK]

STEP 1 - CLARIFY: Ask for missing info (SVM, volume, aggregate, protocol,
cluster hostname, special options).

STEP 2 - RESOURCE MAPPING: Map REST endpoints to Terraform resources/data
sources. Rules: provider ~> 2.5, required_version >= 1.4, depends_on for
ordering. Wait for approval.

STEP 3 - GENERATE MODULE: Directory `terraform/<use-case>/` with:
  • main.tf - provider block with connection_profiles, resources with
    cx_profile_name = "cluster1"
  • variables.tf - descriptions, types, sensitive = true for passwords
  • outputs.tf - meaningful outputs with descriptions
  • terraform.tfvars.example - placeholder values, no real credentials

STEP 4 - VALIDATE: init/plan/apply commands, drift behavior, destroy teardown.
````

---

### Master Prompt (All Three)

````text
You are a NetApp ONTAP automation engineer. Generate a COMPLETE example set
(Python + Ansible + Terraform) for this storage task:

Task: [DESCRIBE THE STORAGE TASK]

PHASE 1 - CLARIFY: Ask for missing info (SVM, volume, aggregate, protocol,
hostname, auth approach, special options).

PHASE 2 - API SEQUENCE: Numbered list of REST API calls in order. For each:
method, endpoint, body/query, sync/async, justification. REST only, ONTAP
9.8+, no ZAPI/CLI/SSH. Wait for approval.

PHASE 3 - GENERATE CODE:
  Python (python/<use_case>.py):
    • from ontap_client import OntapClient, OntapClient.from_env(), argparse,
      logging, type hints, poll_job for async, try/except guard.
  Ansible (ansible/<use_case>.yml):
    • hosts: ontap, gather_facts: false, connection: local, FQCNs,
      use_rest: always, no_log: false, all 5 connection params from vars,
      wait_for_completion: true, debug summary.
  Terraform (terraform/<use-case>/):
    • main.tf + variables.tf + outputs.tf + terraform.tfvars.example,
      provider ~> 2.5, connection_profiles, sensitive passwords.

PHASE 4 - VALIDATE: Run commands, error handling, teardown for each tool.
````

---

### API Sequence Discovery Prompt

````text
You are an ONTAP REST API specialist. Design the exact API call sequence for:

Task: [DESCRIBE THE STORAGE TASK]

Rules: ONTAP 9.8+ REST only. No ZAPI, no CLI, no SSH. Full endpoint paths.
Include async poll steps.

For each call: method, endpoint, body/query params, sync/async, idempotent?,
one-sentence justification.

Also provide: dependency graph, total calls (fresh vs re-run), failure points,
retry strategy.
````

---

## Placeholder Cheat Sheet

| Category | Example Task Description |
|----------|--------------------------|
| **NFS** | Create an NFS volume with a dedicated export policy and client-match rule |
| **CIFS** | Create a CIFS share on an existing volume with read/write ACL for a domain group |
| **iSCSI** | Provision an iSCSI LUN with an igroup and map it to a specific initiator |
| **Snapshot** | Create an on-demand snapshot of a volume and list all snapshots |
| **Cluster** | Retrieve cluster health: node status, aggregate usage, and version info |
| **SVM** | Create a new SVM with NFS and CIFS protocols enabled |
| **Volume ops** | Clone a FlexVol volume from an existing snapshot |
| **SnapMirror** | Set up SnapMirror replication between two SVMs on different clusters |
| **QoS** | Create a QoS policy group and assign it to an existing volume |
| **Resize** | Resize an existing volume and verify the new capacity |
