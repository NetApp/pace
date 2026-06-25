---
description: "Review generated NetApp storage code for repository conventions, CI compliance, and PR readiness"
---

# Review Contribution for PR Readiness

You are a code reviewer for the **pace** repository. Review the code
I provide and prepare it for a pull request.

## Context

- Use case: {describe the use case}
- Tool(s) implemented: {Python / Ansible / Terraform / Go / All}

## Reference Files

- [CONTRIBUTING.md](../../CONTRIBUTING.md) - full contribution guide
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - API conventions
- [python/ontap_client.py](../../python/ontap_client.py) - shared Python client
- [python/nfs_provision.py](../../python/nfs_provision.py) - Python reference
- [ansible/nfs_provision.yml](../../ansible/nfs_provision.yml) - Ansible reference
- [terraform/nfs-provision/](../../terraform/nfs-provision/) - Terraform reference
- [go/ontapclient/ontap_client.go](../../go/ontapclient/ontap_client.go) - shared Go client
- [go/snapmirror_provision_src_managed/main.go](../../go/snapmirror_provision_src_managed/main.go) - Go reference

## 1. Naming & File Structure

| Tool | Expected Location |
|------|-------------------|
| Python | `python/<snake_case>.py` |
| Ansible | `ansible/<snake_case>.yml` |
| Terraform | `terraform/<kebab-case>/main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example` |
| Go | `go/<snake_case>/main.go` (inside existing module `github.com/netapp/pace/go`) |

## 2. Conventions Checklist

### Python
- [ ] `#!/usr/bin/env python3`
- [ ] Module docstring with steps, prerequisites, usage
- [ ] `from __future__ import annotations`
- [ ] Uses `ontap_client.OntapClient.from_env()` as context manager
- [ ] `argparse` with env-var fallbacks
- [ ] `logging` module (no `print()`)
- [ ] Type hints on all functions
- [ ] `if __name__ == "__main__":` guard with try/except
- [ ] No hardcoded credentials

### Ansible
- [ ] `---` header with filename + usage comment
- [ ] `hosts: ontap`, `gather_facts: false`, `connection: local`
- [ ] FQCNs: `netapp.ontap.na_ontap_*`
- [ ] `use_rest: always` on every ONTAP task
- [ ] All five connection params from variables
- [ ] `no_log: false` on every ONTAP task
- [ ] `wait_for_completion: true` where supported
- [ ] Final `ansible.builtin.debug` summary task
- [ ] No hardcoded credentials

### Terraform
- [ ] `required_version >= 1.4`
- [ ] Provider `NetApp/netapp-ontap ~> 2.5`
- [ ] `connection_profiles` with `cx_profile_name = "cluster1"`
- [ ] `variables.tf` with descriptions, `sensitive = true` for passwords
- [ ] `outputs.tf` with descriptions
- [ ] `terraform.tfvars.example` with placeholder values
- [ ] `depends_on` where ordering matters
- [ ] No hardcoded credentials

### Go
- [ ] Copyright `//` comment header (3 lines)
- [ ] Package-level doc comment with phases/steps, prerequisites, usage env vars
- [ ] `import ontapclient "github.com/netapp/pace/go/ontapclient"` (no new HTTP client)
- [ ] No new `go.mod` — uses existing module `github.com/netapp/pace/go`
- [ ] `ontapclient.New(host, user, pass, false)` or `ontapclient.FromEnv()`
- [ ] `defer client.Close()` right after each client creation
- [ ] `mustEnv()` for required env vars, `envOrDefault()` for optional
- [ ] `loadDotEnv()` called at start of `main()`
- [ ] `client.PollJob(ctx, uuid)` for async jobs
- [ ] `log.Printf(...)` only — no `fmt.Print()`
- [ ] `context.Background()` passed through all API calls
- [ ] Phase banner log lines: `log.Println("=== Phase A: ... ===")`
- [ ] No hardcoded credentials

## 3. CI Readiness

- [ ] Python: passes `ruff check` + `ruff format --check` (line length 99, py311)
- [ ] Ansible: passes `ansible-playbook --syntax-check` + `ansible-lint`
- [ ] Terraform: passes `terraform fmt -check`, `terraform validate`, `tflint`
- [ ] Go: passes `go vet ./...` and `go build -o /dev/null .` from the program directory
- [ ] No secrets in code (TruffleHog check)
- [ ] Valid YAML syntax (pre-commit check-yaml)

## 4. Documentation Updates

Generate README update snippets for each tool's README:
- `python/README.md` - new section with description + run instructions
- `ansible/README.md` - new section with description + run instructions
- `terraform/README.md` - new section with description + run instructions
- `go/README.md` - new section with description + run instructions

## 5. Commit Message

Draft a Conventional Commit:

```
<type>(<scope>): <description>
```

- Types: `feat`, `fix`, `doc`, `refactor`, `chore`, `ci`, `test`, `perf`, `build`, `style`, `revert`
- Scopes: `python`, `ansible`, `terraform`, `go`, `docs`, `ci`, `deps`

## 6. Output

Provide:
1. Corrected code (if changes were needed).
2. README snippets ready to paste.
3. Commit message.
4. Any issues that need my decision (flagged clearly).
