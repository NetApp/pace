## Summary

<!-- Brief description of what this PR does and why. -->

## Changes

-

## Checklist

**General**
- [ ] No secrets, credentials, or API tokens in code or config

**If touching `python/`**
- [ ] Scripts compile (`python -m py_compile python/*.py`)
- [ ] Lint passes (`ruff check python/`)

**If touching `ansible/`**
- [ ] Syntax check passes (`ansible-playbook --syntax-check`)
- [ ] `ansible-lint` passes

**If touching `terraform/`**
- [ ] `terraform fmt -check` passes
- [ ] `terraform validate` passes

## Test Report

<!-- TEST_REPORT_REQUIRED: contributors MUST fill this in. See TESTING.md. -->
<!-- Delete this entire section ONLY for docs-only or CI-only PRs (no files under python/, ansible/, terraform/). -->

**Environment:** <!-- e.g. ONTAP Simulator / ONTAP Select / Real cluster / Cloud Volumes ONTAP -->
**ONTAP version:** <!-- e.g. 9.14.1P3 -->
**Style touched:** <!-- python | ansible | terraform | multiple -->

### First run

<details><summary>Command + output</summary>

```text
$ <command here>
<paste 10-50 lines of output, redact secrets>
```

</details>

### Idempotency / re-run

<details><summary>Second-run evidence</summary>

```text
$ <same command, run again>
<for ansible: PLAY RECAP must show changed=0>
<for terraform: `terraform plan` must show "No changes">
<for python: explain expected behavior on re-run>
```

</details>

### Cleanup / teardown

<details><summary>Teardown evidence (skip for read-only examples)</summary>

```text
$ <teardown command>
<paste output>
```

</details>

### Cannot run on a cluster?

<!-- If you couldn't run end-to-end, explain why here and apply the
     'needs-test-run' label so a maintainer can run it. Otherwise delete
     this subsection. -->

## Related issues

<!-- Link any related issues: Fixes #123, Relates to #456 -->
