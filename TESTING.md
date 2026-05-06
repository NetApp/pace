# Testing

Pace ships *runnable examples*, not a library. Every PR that adds or
modifies an example under `python/`, `ansible/`, or `terraform/` must
include a populated **Test Report** in the PR body so reviewers can see
the example actually worked end-to-end against an ONTAP cluster.

This document defines what to capture. The PR template
([.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md))
ships the section ready to fill in.

---

## What we mean by "tested"

Two layers, with clear ownership:

| Layer                | Who runs it    | What it checks                                          |
| -------------------- | -------------- | ------------------------------------------------------- |
| **Static checks**    | CI (automatic) | Lint, format, syntax, secret scan, YAML parse           |
| **End-to-end run**   | Contributor    | The example actually does what it claims, on a cluster  |

Static checks are non-negotiable and gate the PR (see
[CONTRIBUTING.md](CONTRIBUTING.md#ci-expectations)). End-to-end evidence
is contributor-supplied in the PR body. A reviewer will not approve a
PR that lacks the Test Report.

---

## Accepted environments

Any of the following is acceptable. Just declare which one you used and
the exact ONTAP version (output of `cluster show -fields version` or the
`/cluster` REST endpoint).

| Environment              | Notes                                                          |
| ------------------------ | -------------------------------------------------------------- |
| **ONTAP Simulator**      | Free; great for most provisioning examples                     |
| **ONTAP Select**         | Software-defined; good for multi-node features                 |
| **Real ONTAP cluster**   | 9.8 or newer (matches the API floor used by every example)     |
| **Cloud Volumes ONTAP**  | Acceptable; mention the cloud and instance type                |

If your change can only be exercised on hardware not available in the
simulator (e.g., a feature requiring physical disks of a certain type),
say so explicitly in the **Cannot run on a cluster?** section of the
report so a reviewer with the right environment can run it.

---

## Per-style evidence

Pick the style(s) your PR touches and capture the matching evidence.

### Python (`python/`)

1. **First run** — execute the script with realistic args:

   ```bash
   python <script>.py --svm <svm> --volume <vol> ...
   ```

   Capture stdout (10-50 lines is usually enough) and the exit code.

2. **Re-run safety** — run the same command again. Either:
   - the script is idempotent and exits 0 with no destructive change, or
   - the script detects the existing state and reports it, or
   - if the script is intentionally not re-runnable, document that in
     the report so reviewers know what to expect.

3. **Cleanup** — if the script created resources, show the commands
   used to remove them (often a separate teardown script or REST `DELETE`
   calls). One-shot read-only scripts can skip this.

### Ansible (`ansible/`)

1. **First run** — run the playbook:

   ```bash
   ansible-playbook -i inventory/hosts.yml <playbook>.yml
   ```

   Capture the **PLAY RECAP** line — `ok=`, `changed=`, `failed=`.

2. **Idempotency** — re-run the same command immediately. The recap
   **must report `changed=0`**. This is the canonical Ansible
   idempotency proof. If the recap shows `changed > 0` on the second
   run, the playbook is not idempotent and should be fixed before
   review.

3. **Teardown** — for provisioning playbooks, run the corresponding
   `state: absent` task or a teardown playbook and capture its recap.
   Read-only fact-gathering playbooks can skip this.

### Terraform (`terraform/`)

The full lifecycle is the test. Capture each step:

1. `terraform init`
2. `terraform plan` — should show the resources to be created.
3. `terraform apply` — capture the *Apply complete!* summary line.
4. `terraform plan` again — **must report `No changes`** (drift / idempotency proof).
5. `terraform destroy` — capture the *Destroy complete!* line.
6. `terraform plan` once more — should again report `No changes`
   (clean teardown proof).

For data-source-only modules (no resources), steps 1-3 plus the
*Apply complete!* line are enough.

---

## Output excerpt rules

- **Length** — paste 10-50 lines per command. Truncate the middle with
  `# ... <N> lines elided ...` if needed.
- **Redaction** — replace cluster hostnames, serial numbers, license
  keys, IP addresses, and SVM names if they are sensitive. Use placeholders
  like `cluster-1.example.com`, `10.0.0.1`, `svm0`. Do **not** redact
  ONTAP version, return codes, counts, or error messages — those are
  the parts reviewers need.
- **Format** — wrap output in fenced code blocks with the `text`
  language tag for readability.

---

## Cannot run on a cluster?

If you genuinely cannot run the example end-to-end (no access to a
suitable cluster, feature gated to hardware you do not have, etc.):

1. Say so explicitly in the report.
2. Describe what *would* be the expected output.
3. Tag the PR with the `needs-test-run` label so a maintainer with
   access can run it before merge.

This is an escape hatch, not the default path. PRs without
end-to-end evidence and without a credible reason will be sent back.

---

## Soft gate

A workflow checks the PR body for a populated Test Report and, when it
looks empty, applies a `needs-test-report` label and posts a sticky
comment pointing here. The check is informational — it does not fail
the build — but reviewers will not approve a PR carrying that label.
