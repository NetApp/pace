# Generate an Orchestrio Step Definition

Given an ONTAP REST API endpoint, a shell task, or a plain-English description,
generate a single Orchestrio step definition or a reusable step fragment YAML file.

> For ONTAP REST API conventions (endpoints, auth, headers, response shapes, async jobs),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Rules

1. A step must have `name` (snake_case matching `^[a-zA-Z_][a-zA-Z0-9_]*$`), `type`, and `config`.
2. Available types: `http` (REST calls) and `shell` (subprocess commands).
3. Use `{{ env.VAR }}` for any value that should be supplied at runtime — never hardcode
   secrets, hosts, or user-specific values.
4. For `http` steps, set `config.method`, `config.url`, and optionally `config.body`,
   `config.headers`, `config.timeout`. Follow the API patterns in `docs/ontap-api-patterns.md`.
5. For `shell` steps, set `config.command`. Use `{{ steps.<name>.<path> }}` or
   `{{ env.VAR }}` inside the command.
6. Add `retry` for network-dependent or discovery operations (see retry guidance in
   `docs/ontap-api-patterns.md`).
7. For asynchronous ONTAP operations, generate a companion poll step using the
   `ontap_poll_job.yaml` fragment.

## Reusable fragment rules

If the step is generic enough to be reused across workflows, generate it as a **step fragment**:

1. Add a comment header documenting expected env vars and recommended defaults.
2. The filename should match the step name: `ontap_<operation>.yaml` for a step named `<operation>`.
3. Place fragments in the `steps/` directory.
4. Omit auth fields (`username`, `password`, `headers`, `verify_ssl`) when they should come
   from the workflow's `defaults:` block.

## Output format

1. Return a single YAML code block for the step or fragment.
2. If it is a reusable fragment, also return an `include:` snippet showing usage in a workflow.
3. If the operation is asynchronous, also return a companion poll step.
4. List all env vars the step expects.

## Example — Inline step (GET)

```yaml
- name: get_aggregates
  type: http
  config:
    method: GET
    url: "https://{{ env.ONTAP_HOST }}/api/storage/aggregates?fields=name,space,state&return_timeout=30"
    timeout: 30
```

## Example — Reusable fragment (POST + async job)

Fragment (`steps/ontap_create_snapshot.yaml`):

```yaml
# Reusable step: create a snapshot on an ONTAP volume.
# Expects env: ONTAP_HOST, VOLUME_UUID, SNAPSHOT_NAME
# Best used with defaults for auth (username/password/headers/verify_ssl).
name: create_snapshot
type: http
config:
  method: POST
  url: "https://{{ env.ONTAP_HOST }}/api/storage/volumes/{{ env.VOLUME_UUID }}/snapshots"
  headers:
    Content-Type: "application/json"
  timeout: 60
  body:
    name: "{{ env.SNAPSHOT_NAME }}"
```

Usage in a workflow:

```yaml
steps:
  - include: ../steps/ontap_create_snapshot.yaml

  - include: ../steps/ontap_poll_job.yaml
    override:
      name: track_snapshot_job
      config:
        url: "https://{{ env.ONTAP_HOST }}/api/cluster/jobs/{{ steps.create_snapshot.body.job.uuid }}?fields=state,message&return_timeout=120"
        poll:
          interval_seconds: 5
```
