# Chain Step Outputs with Template Expressions

Given the JSON response shapes of prior steps, generate the correct
`{{ steps.<name>.<path> }}` template expressions to pass data from one step to the next.

> For ONTAP REST API response shapes and common access patterns,
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Template syntax

Orchestrio resolves `{{ steps.<step_name>.<path> }}` by walking the step's result object:

- **`steps.<name>.body`** — the parsed JSON response body.
- **Dot notation** for nested fields: `steps.get_cluster.body.version.full`
- **Numeric index** for arrays: `steps.get_volume.body.records.0.uuid`
- **`steps.<name>.status_code`** — HTTP status code (integer).
- **`env.VAR`** — environment variable (can be mixed in the same string).

Templates can appear in any string value: `url`, `command`, `body` fields, headers, etc.

## Rules

1. `<step_name>` must exactly match the step's `name:` field (or the overridden name for
   included fragments).
2. A step can only reference outputs from steps that executed **before** it. Referencing
   a later step or a skipped step causes a template resolution error.
3. Numeric array indices are zero-based: `.records.0`, `.records.1`, etc.
4. Templates are resolved as strings. When embedded in a URL or command, surround with
   quotes if the value might contain special characters.
5. You can chain multiple templates in one string:
   ```yaml
   command: "echo 'Cluster {{ steps.get_cluster.body.name }} has {{ steps.get_nodes.body.num_records }} nodes'"
   ```
6. For POST/PATCH steps that return a job, always wire the job UUID to a poll step.

## Output format

1. For each pair of steps (producer -> consumer), show the JSON shape of the producer's
   output and the exact template expression the consumer should use.
2. Return the consumer step YAML with the templates filled in.
3. Flag any forward references or missing fields.

## Example

Given these steps in order:

**Step 1** — `create_volume` (POST) returns:
```json
{ "job": { "uuid": "abc-123" } }
```

**Step 2** — `track_create_job` (poll) returns:
```json
{ "state": "success", "message": "Volume created." }
```

**Step 3** — `get_volume` (GET) returns:
```json
{ "records": [{ "uuid": "vol-uuid-789", "name": "my_vol" }], "num_records": 1 }
```

The chained template expressions are:

```yaml
# Step 2 needs job UUID from step 1
- include: ../steps/ontap_poll_job.yaml
  override:
    name: track_create_job
    config:
      url: "https://{{ env.ONTAP_HOST }}/api/cluster/jobs/{{ steps.create_volume.body.job.uuid }}?fields=state,message&return_timeout=120"

# Step 4 uses volume UUID from step 3
- name: assign_policy
  type: http
  config:
    method: PATCH
    url: "https://{{ env.ONTAP_HOST }}/api/storage/volumes/{{ steps.get_volume.body.records.0.uuid }}"
    headers:
      Content-Type: "application/json"
    body:
      nas:
        export_policy:
          name: "{{ env.VOLUME_NAME }}_policy"

# Summary uses outputs from multiple prior steps
- name: print_summary
  type: shell
  config:
    command: >-
      echo "Volume '{{ steps.get_volume.body.records.0.name }}' — job {{ steps.track_create_job.body.state }}: {{ steps.track_create_job.body.message }}"
```
