## Summary

<!-- Brief description of what this PR does and why. -->

## Changes

- 

## Checklist

**General**
- [ ] No secrets, credentials, or API tokens in code or config

**If touching `yaml-workflows/`**
- [ ] Workflow YAML validates against `yaml-workflows/workflow-spec/v1/schema.json`
- [ ] Executor lint passes (`ruff check yaml-workflows/executor/orchestrio/`)
- [ ] Executor tests pass (`pytest yaml-workflows/executor/tests/ -v`)

**If touching `python/`**
- [ ] Scripts compile (`python -m py_compile python/*.py`)
- [ ] Lint passes (`ruff check python/`)

**If touching `ansible/`**
- [ ] Syntax check passes (`ansible-playbook --syntax-check`)
- [ ] `ansible-lint` passes

**If touching `terraform/`**
- [ ] `terraform fmt -check` passes
- [ ] `terraform validate` passes

## Related issues

<!-- Link any related issues: Fixes #123, Relates to #456 -->
