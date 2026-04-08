# Create a Reusable Step Fragment

Given a description of a single reusable operation, generate an Orchestrio step
fragment YAML file that can be imported via `include:` in any workflow.

> For ONTAP REST API conventions (endpoints, auth, headers, response shapes, async jobs),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Rules

1. A step fragment is a single YAML file containing exactly one step definition.
2. The step must have `name` (snake_case), `type`, and `config`.
3. Use `{{ env.VAR }}` for any value that should be supplied by the calling workflow.
4. The filename should match the step name: `ontap_get_cluster.yaml` for a step named `get_cluster`.
5. Place fragments in the `steps/` directory.
6. Add `retry` config for network-dependent operations.
7. Omit auth fields (`username`, `password`, `headers`, `verify_ssl`) — these come from the
   workflow's `defaults:` block.
8. The calling workflow can override any field via the `include:` override block.

## Output format

Return a single YAML code block for the fragment, plus an example `include:` snippet
showing how a workflow would use it.

## Example

Fragment (`steps/ontap_get_cluster.yaml`):

```yaml
# Reusable step: fetch cluster version info.
# Expects env: ONTAP_HOST
# Best used with defaults for auth (username/password/headers/verify_ssl).
name: get_cluster
type: http
config:
  method: GET
  url: "https://{{ env.ONTAP_HOST }}/api/cluster?fields=version&return_timeout=120"
```

Usage in a workflow:

```yaml
steps:
  - include: steps/ontap_get_cluster.yaml
```

With overrides:

```yaml
steps:
  - include: steps/ontap_get_cluster.yaml
    override:
      name: get_cluster_full
      config:
        url: "https://{{ env.ONTAP_HOST }}/api/cluster?fields=*"
```
