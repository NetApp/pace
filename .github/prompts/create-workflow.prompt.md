# Create an Orchestrio Workflow

Given a plain-English description of what the workflow should do, generate a valid
Orchestrio workflow YAML file.

## Rules

1. Every workflow must have `name` (kebab-case), `version: "1"`, and a `steps` array.
2. Each step must have `name` (snake_case matching `^[a-zA-Z_][a-zA-Z0-9_]*$`), `type`, and `config`.
3. Available step types: `http` (REST calls) and `shell` (subprocess commands).
4. Use `{{ env.VAR_NAME }}` for credentials and host addresses — never hardcode secrets.
5. Use `{{ steps.<step_name>.<path> }}` to reference output from earlier steps.
6. Add `retry: { attempts: N, delay_seconds: N }` for flaky network calls.
7. Set `on_failure: continue` on non-critical steps; default is `stop`.
8. Use a `defaults:` block when multiple steps of the same type share config (headers, auth, timeout).
9. Add a `description:` field explaining what the workflow does.
10. For ONTAP workflows, include `verify_ssl: false` and `X-Dot-Client-App: orchestrio` header.

## Output format

Return a single YAML code block. Add a brief comment before each step explaining its purpose.

## Example

```yaml
name: example-workflow
version: "1"
description: Fetch cluster info and print the version.

env:
  ONTAP_HOST: ""
  ONTAP_USER: "admin"
  ONTAP_PASS: ""

steps:
  - name: get_cluster
    type: http
    config:
      method: GET
      url: "https://{{ env.ONTAP_HOST }}/api/cluster?fields=version"
      username: "{{ env.ONTAP_USER }}"
      password: "{{ env.ONTAP_PASS }}"
      verify_ssl: false

  - name: print_version
    type: shell
    config:
      command: "echo 'Version: {{ steps.get_cluster.body.version.full }}'"
```
