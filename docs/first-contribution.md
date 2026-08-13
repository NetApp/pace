# Your first Pace contribution

A 7-step walkthrough from "I just found this repo" to "my PR is merged."

**Estimated time:** ~45 minutes for a small change, plus a CI cycle.

If you get stuck on any step, comment on your PR or open a
[Discussion](https://github.com/NetApp/pace/discussions) — typical
response time is 1 business day.

| Step | What you'll do | Time |
|------|----------------|------|
| 1 | Sign the NetApp CCLA | 5 min |
| 2 | Fork & clone | 3 min |
| 3 | Set up your local environment | 5 min |
| 4 | Pick a `good first issue` | 2 min |
| 5 | Make the change | 10–25 min |
| 6 | Open a Pull Request | 2 min |
| 7 | Address review feedback & merge | 10–15 min |

---

## Step 1 — Sign the NetApp CCLA

NetApp will not review any PR until the
[Corporate Contributor License Agreement](https://netapp.tap.thinksmart.com/prod/Portal/ShowWorkFlow/AnonymousEmbed/3d2f3aa5-9161-4970-997d-e482b0b033fa)
is on file. **Project name:** `NetApp/pace`.

This is a one-time step per person/employer. If you skip it, the rest
of your effort is wasted, so do it first.

---

## Step 2 — Fork the repo and clone your fork

On GitHub, click **Fork** in the top-right of
[github.com/NetApp/pace](https://github.com/NetApp/pace). This creates
`<your-username>/pace`.

```bash
git clone https://github.com/<your-username>/pace.git
cd pace
git remote add upstream https://github.com/NetApp/pace.git
```

The `upstream` remote lets you sync future changes from the project:

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

---

## Step 3 — Set up your local environment

You need **Python 3.11+** and **make**. That's it for typo fixes and
docs changes. For example-code changes you'll also want **Ansible**
and/or **Terraform** and/or **Go 1.22+** (only the one your change touches).

```bash
make install        # creates .venv/ and installs ruff
make hooks          # installs pre-commit (lint + commitlint + secret scan)
```

Verify everything works:

```bash
make ci             # runs the same lint that CI runs (~10s)
```

If `make ci` fails on the unchanged `main` branch, something's wrong
with your install — see
[troubleshooting.md § Pre-commit and CI](troubleshooting.md#pre-commit-and-ci).

> **Prefer not to install Python toolchains?** The repo ships a
> [Dockerfile](../Dockerfile) and [`docker-compose.yml`](../docker-compose.yml).
> Run `make docker-ci` to run all checks in a sandbox container.

---

## Step 4 — Pick a `good first issue`

Browse the
[good first issues label](https://github.com/NetApp/pace/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
and find one whose **Estimated time** matches what you have. Each
curated good-first-issue spells out:

- **Exact files to change** (no guessing)
- **Expected outcome** (what should be true after the change)
- **How to test** (commands + expected output)
- **ONTAP concepts touched** (links to [`ontap-in-5-minutes.md`](ontap-in-5-minutes.md))

**Comment on the issue saying you'd like to take it** so a maintainer
can assign it — this prevents two people doing the same work.

> **No good-first-issue open?** Pick a small enhancement to a Python
> example: add one more piece of cluster info to the output, expose
> one more CLI flag, or improve an error message. PRs in that pattern
> are reliably merged in 1–2 review rounds.

---

## Step 5 — Make the change

### 5a. Create a branch

Branch names follow [`CONTRIBUTING.md` § Branch naming](../CONTRIBUTING.md#branch-naming):

```bash
git checkout -b feature/<short-description>   # e.g. feature/print-ontap-version
```

### 5b. Edit the file

Open the file the issue points at. If you're new to NetApp ONTAP, read
[`ontap-in-5-minutes.md`](ontap-in-5-minutes.md) and the "Concepts used"
comment at the top of the example file before editing.

### 5c. Run checks locally

Before committing, run the same lint your PR will face:

```bash
make ci                  # Python lint + format + copyright headers + go vet
make ansible-lint        # only if you touched ansible/
make terraform-validate  # only if you touched terraform/
make go-vet              # only if you touched go/
```

The pre-commit hooks installed in Step 3 also run automatically on
`git commit`. They auto-fix simple lint issues — when they do, just
`git add .` and commit again.

### 5d. Commit using Conventional Commits

```bash
git add <files>
git commit -m "feat(python): print ontap version in cluster_info"
```

Format: `<type>(<scope>): <description>`.

| Valid types | Valid scopes |
|---|---|
| `build, chore, ci, doc, feat, fix, perf, refactor, revert, style, test` | `python, ansible, terraform, go, docs, ci, deps` |

If commitlint rejects your message:

```bash
git commit --amend -m "feat(python): print ontap version in cluster_info"
```

---

## Step 6 — Open a Pull Request

Push your branch:

```bash
git push -u origin feature/<short-description>
```

GitHub will print a link. Click it. The PR template appears — fill in
the **Summary**, **Changes**, and (if you touched `python/`, `ansible/`,
`terraform/`, or `go/`) the **Test Report** section.

### About the Test Report

If your change runs against a NetApp storage system, reviewers need
proof it actually worked. See [TESTING.md](../TESTING.md) — it tells
you exactly what to capture (typically: command + first-run output +
re-run output + teardown). 10–50 lines per command is plenty.

**Don't have a cluster?** Get the
[free ONTAP Simulator](https://mysupport.netapp.com/site/tools/tool-eula/ontap-9-simulator)
(NetApp account required), or say so in the **Cannot run on a cluster?**
subsection and apply the `needs-test-run` label so a maintainer with
access can run it for you.

**Doc-only or CI-only PRs** are auto-detected and don't need a Test
Report — you'll see the `docs-only` or `ci-only` label appear within
~30 seconds of opening the PR, and the soft-gate skips itself.

---

## Step 7 — Address review feedback & merge

### What runs automatically

Within ~2 minutes of opening the PR you'll see:

| Check | What it does |
|---|---|
| **CI** | Lint, format, README check, copyright headers |
| **PR Guard** | Commitlint, secret scan, YAML syntax |
| **Validate Examples** | Only if you touched `ansible/`, `terraform/`, or `go/` |
| **PR Labeler** | Path-based labels (`python`, `ansible`, `terraform`, `go`, `docs`, `ci`) appear within 30s |
| **Welcome bot** | Greets first-time contributors with orientation links |
| **Test Report Check** | Soft gate, applies `needs-test-report` label if your PR needs evidence |
| **Explain CI failure** | If anything fails, posts a comment with the **exact fix command** so you don't read raw logs |

### How to respond to a red check

1. Read the **Explain CI failure** comment that appears on the PR.
2. Run the suggested command locally.
3. Commit and push the fix. The check re-runs automatically.
4. The sticky comment updates with the next failure (or stays put if
   the same check fails again).

### How to respond to reviewer comments

[CODEOWNERS](../.github/CODEOWNERS) auto-assigns reviewers. They
typically respond within 1–2 business days. Address each comment with
a code change or a reply, then re-request review via the GitHub UI.

### Merge

Once you have a green CI + an approving review, a maintainer will
**Squash and merge** your PR. Your contribution is in. The
[CHANGELOG.md](../CHANGELOG.md) updates on the next release.

---

## What if I get really stuck?

| Stuck on… | Where to go |
|---|---|
| Setup or install errors | [`troubleshooting.md` § Pre-commit and CI](troubleshooting.md#pre-commit-and-ci) |
| ONTAP terminology | [`ontap-in-5-minutes.md`](ontap-in-5-minutes.md) |
| API conventions | [`ontap-api-patterns.md`](ontap-api-patterns.md) |
| What goes in a Test Report | [`TESTING.md`](../TESTING.md) |
| Anything else | Comment on your PR, or open a [Discussion](https://github.com/NetApp/pace/discussions) |

Welcome to Pace.
