# Create an Orchestrio Workflow

Given a plain-English description of what the workflow should do, generate a valid
Orchestrio workflow YAML file.

> For ONTAP REST API conventions (endpoints, auth, headers, response shapes, async jobs),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Rules

1. Every workflow must have `name` (kebab-case), `version: "1"`, and a `steps` array.
2. Each step must have `name` (snake_case matching `^[a-zA-Z_][a-zA-Z0-9_]*$`), `type`, and `config`.
3. Available step types: `http` (REST calls) and `shell` (subprocess commands).
4. Use `{{ env.VAR_NAME }}` for credentials and host addresses — never hardcode secrets.
5. Use `{{ steps.<step_name>.<path> }}` to reference output from earlier steps.
6. Add `retry: { attempts: N, delay_seconds: N }` for flaky network calls.
7. Set `on_failure: continue` on non-critical steps; default is `stop`.
8. Use a `defaults:` block when multiple steps of the same type share config.
9. Add a `description:` field explaining what the workflow does.

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

defaults:
  http:
    headers:
      Accept: "application/hal+json"
      X-Dot-Client-App: "orchestrio"
    username: "{{ env.ONTAP_USER }}"
    password: "{{ env.ONTAP_PASS }}"
    timeout: 30
    verify_ssl: false

steps:
  # Fetch cluster version
  - name: get_cluster
    type: http
    config:
      method: GET
      url: "https://{{ env.ONTAP_HOST }}/api/cluster?fields=version"

  # Print version
  - name: print_version
    type: shell
    config:
      command: "echo 'Version: {{ steps.get_cluster.body.version.full }}'"
```
