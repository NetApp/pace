<!-- Generated from ai/shared/prompt-catalog.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# AI prompt catalog

This repository ships reusable prompts for generating NetApp storage automation:
one for planning an API sequence, one per tool for generating code, one that
generates all four at once, and one for reviewing the result before a PR.

Each prompt is authored once in [`ai/`](../ai/README.md) and generated into every
format the supported assistants read, so the same prompt is available whichever
editor you use.

## Where the prompts show up

| Tool | Reads | How to invoke |
|------|-------|---------------|
| GitHub Copilot (VS Code, github.com) | `.github/prompts/*.prompt.md` | Type `/` in Copilot Chat |
| Cursor | `.cursor/commands/*.md` | Type `/` in the chat panel |
| Any other assistant | the prompt files themselves | Paste the file contents |

Commands are named `<product>-<task>`, so typing `/ontap-` lists everything
scoped to ONTAP.

## Available prompts

| Command | What it does | Prompt text |
|---------|--------------|-------------|
| `/ontap-generate-ansible` | Generate an Ansible playbook that automates a NetApp storage task using REST APIs | [ai/ontap/generate-ansible.md](../ai/ontap/generate-ansible.md) |
| `/ontap-generate-go` | Generate a Go program that automates a NetApp storage task using REST APIs | [ai/ontap/generate-go.md](../ai/ontap/generate-go.md) |
| `/ontap-generate-python` | Generate a Python script that automates a NetApp storage task using REST APIs | [ai/ontap/generate-python.md](../ai/ontap/generate-python.md) |
| `/ontap-generate-terraform` | Generate a Terraform module that automates a NetApp storage task using REST APIs | [ai/ontap/generate-terraform.md](../ai/ontap/generate-terraform.md) |
| `/ontap-generate-workflow` | Generate a complete NetApp storage workflow - Python + Ansible + Terraform + Go - for a storage task | [ai/ontap/generate-workflow.md](../ai/ontap/generate-workflow.md) |
| `/ontap-plan-api-sequence` | Design the REST API call sequence for a NetApp storage operation before writing code | [ai/ontap/plan-api-sequence.md](../ai/ontap/plan-api-sequence.md) |
| `/review-contribution` | Review generated NetApp storage code for repository conventions, CI compliance, and PR readiness | [ai/shared/review-contribution.md](../ai/shared/review-contribution.md) |

For an assistant with no slash-command support - ChatGPT, Gemini, Claude, and
the like - open the prompt file in the last column and paste its contents into
the chat, then replace `{task description}` with your task. The file is the
prompt; there is no separate copy to keep in sync.

## Using one

1. Open the chat panel, type `/`, and pick the command.
2. Replace `{task description}` with your storage task.
3. Work through the prompt's steps. Most stop and ask you to confirm the API
   sequence before they write any code - that checkpoint is the point.

A typical run through a new use case:

```
1.  /ontap-plan-api-sequence   →  Design and validate the REST API sequence
2.  /ontap-generate-workflow   →  Generate Python + Ansible + Terraform + Go
    (or /ontap-generate-python, -ansible, -terraform, -go individually)
3.  /review-contribution       →  Check conventions, CI compliance, README updates
```

## Conventions attach on their own

Product conventions are not prompts you invoke. They are attached
automatically when you edit files in that product's directories - through
`.github/instructions/` for Copilot and `.cursor/rules/` for Cursor - so a file
under `python/ontap/` picks up the ONTAP rules without you asking.

Repo-wide context works the same way through `AGENTS.md`, which Cursor and most
other agents read, and `.github/copilot-instructions.md` for Copilot.

## AI output is a draft

Every prompt produces a starting point, not a merge. Run `make ci`, validate
against a real cluster, and record the result in the PR's
[Test Report](../TESTING.md) - the same bar as any hand-written change.

## Editing the prompts

Everything under `.github/prompts/`, `.github/instructions/`, `.cursor/`, plus
`AGENTS.md`, `.github/copilot-instructions.md`, and this page, is generated.
Edit the source in [`ai/`](../ai/README.md) and run `make ai-assets`; CI fails if
the two drift apart.

## Task description cheat sheet

Prompts expect a one-line task description. Examples that work well:

| Category | Example task description |
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
