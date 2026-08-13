---
kind: shared
description: "Repo-wide context, layout, and conventions for the pace repository"
---

# Working in the Pace repository

## Project overview

This repository contains NetApp storage automation examples in Python, Ansible,
Terraform, and Go. Each approach implements the same use cases so users can
compare side-by-side and pick the tool their team already knows.

Python and Go are both imperative scripting; Ansible is declarative; Terraform
is stateful. The repository presents three styles across four tools.

## Repository layout

Examples are grouped first by tool, then by the NetApp product they target:

```
python/<product>/       # Python script examples (snake_case files)
ansible/<product>/      # Ansible playbook examples (snake_case files)
terraform/<product>/    # Terraform module examples (kebab-case dirs)
go/<product>/           # Go program examples (snake_case subdirs, one main.go each)
docs/                   # Guides, API patterns, comparison docs
ai/                     # Source of truth for these instructions and the prompts
```

Products: `ontap` holds every example today. `console` (NetApp Console) adds a
deployment level — `<tool>/console/local/` — and is currently an empty
placeholder. Put new work under the product it targets; never at the tool root.

Product-specific conventions live alongside the code they govern and are
attached automatically when you work in that product's directories.

## Reusable prompts

Task prompts are available as slash commands in both GitHub Copilot and Cursor.
They are named `<product>-<task>`, so typing `/ontap-` lists everything scoped
to ONTAP.

{{PROMPT_INDEX}}

## Coding conventions

- Python >= 3.11; use modern syntax (PEP 604 unions, f-strings, `match` where appropriate).
- Linter: `ruff` (line length 99, target py311). Run `ruff check python/`.
- All new Python code should have type hints.
- Go 1.22+.
- Never hardcode credentials - use env vars, Ansible Vault, or Terraform `sensitive`.
- Every generated source file (`.py`, `.yml`, `.tf`, `.sh`, `.html`, `.go`) MUST start
  with the standard NetApp copyright header (see below).

## Copyright header (required on all source files)

Use the comment syntax of the file. Year is `2026`. Full trademark text
lives in `NOTICE`; do not duplicate it in source files.

```text
© 2026 NetApp, Inc. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
See the NOTICE file in the repo root for trademark and attribution details.
```

The `insert-license` pre-commit hook adds and verifies it automatically.
Exempt files: Markdown, `requirements.*`, `ansible/*/inventory/*`,
`ansible/*/group_vars/*`, `*.example`, `dependabot.yml`.

## Editing these instructions

`AGENTS.md`, `.github/copilot-instructions.md`, `.github/prompts/`,
`.github/instructions/`, and `.cursor/` are all generated. Edit the matching
file under `ai/` and run `make ai-assets`; CI fails if the two drift apart.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the full flow.
