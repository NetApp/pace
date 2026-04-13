# ONTAP REST API Patterns

Canonical reference for ONTAP REST API conventions used across all automation
examples in this repository (Python, Ansible, Terraform, and YAML workflows).
For the full API specification, see the
[ONTAP REST API documentation](https://docs.netapp.com/us-en/ontap-restapi/swagger-ui/index.html).

## Base URL

All ONTAP REST endpoints follow this pattern:

```
https://<cluster-management-ip-or-hostname>/api/<category>/<resource>
```

In Orchestrio templates: `https://{{ env.ONTAP_HOST }}/api/...`

## Authentication

| Field | Value | Notes |
|-------|-------|-------|
| `username` | `{{ env.ONTAP_USER }}` | Basic auth — typically `admin` |
| `password` | `{{ env.ONTAP_PASS }}` | Never hardcode; always use env template |
| `verify_ssl` | `false` | Required for lab / self-signed certs |

## Standard Headers

| Header | Value | When |
|--------|-------|------|
| `Accept` | `application/hal+json` | All requests |
| `X-Dot-Client-App` | `orchestrio` | All requests (client identification) |
| `Content-Type` | `application/json` | POST and PATCH requests |

In Orchestrio, declare these once in the workflow `defaults:` block:

```yaml
defaults:
  http:
    headers:
      Accept: "application/hal+json"
      X-Dot-Client-App: "orchestrio"
    username: "{{ env.ONTAP_USER }}"
    password: "{{ env.ONTAP_PASS }}"
    timeout: 30
    verify_ssl: false
```

## Query Parameters

| Parameter | Usage | Example |
|-----------|-------|---------|
| `fields` | Select which fields to return | `?fields=name,uuid,space` |
| `name` | Filter by name | `?name=vol1` |
| `svm.name` | Filter by SVM | `?svm.name=vs0` |
| `return_timeout` | Server-side wait (seconds) before returning | `&return_timeout=30` |
| `max_records` | Limit number of returned records | `&max_records=100` |

Combine with `&`: `?name={{ env.VOLUME_NAME }}&svm.name={{ env.SVM_NAME }}&fields=name,uuid&return_timeout=30`

## Response Shapes

### Collection (GET with query)

Returned when querying a list of resources (e.g. volumes, nodes, export policies).

```json
{
  "records": [
    { "uuid": "abc-123", "name": "vol1" },
    { "uuid": "def-456", "name": "vol2" }
  ],
  "num_records": 2,
  "_links": { "self": { "href": "/api/storage/volumes?name=vol1" } }
}
```

Template access:
- `{{ steps.<name>.body.records.0.uuid }}` — first record UUID
- `{{ steps.<name>.body.records.0.name }}` — first record name
- `{{ steps.<name>.body.num_records }}` — total count

### Single Resource (GET by UUID)

Returned when fetching a specific resource by its UUID.

```json
{
  "uuid": "abc-123",
  "name": "cluster1",
  "version": { "full": "9.14.1", "generation": 9, "major": 14, "minor": 1 }
}
```

Template access:
- `{{ steps.<name>.body.name }}`
- `{{ steps.<name>.body.version.full }}` — nested fields via dot notation

### Async Job (POST / PATCH response)

Many write operations (volume create, move, policy assign) return a job reference
instead of completing synchronously.

```json
{
  "job": {
    "uuid": "job-uuid-123",
    "_links": { "self": { "href": "/api/cluster/jobs/job-uuid-123" } }
  }
}
```

Template access:
- `{{ steps.<name>.body.job.uuid }}` — used to construct the poll URL

### Job Poll Result

Returned by `GET /api/cluster/jobs/{uuid}` after polling completes.

```json
{
  "uuid": "job-uuid-123",
  "state": "success",
  "message": "Volume created successfully.",
  "description": "POST /api/storage/volumes"
}
```

Job states: `queued`, `running`, `success`, `failure`.

Template access:
- `{{ steps.<poll_name>.body.state }}`
- `{{ steps.<poll_name>.body.message }}`

## Async Job Flow

Any POST or PATCH that triggers a long-running operation returns a `job` object.
The standard pattern in Orchestrio is:

1. **Trigger** — POST/PATCH returns `{ "job": { "uuid": "..." } }`
2. **Poll** — GET `/api/cluster/jobs/{uuid}?fields=state,message&return_timeout=120` until `state != running`
3. **Continue** — use the poll result's `state` and `message` in downstream steps

In Orchestrio, use the `ontap_poll_job.yaml` fragment:

```yaml
- include: ../steps/ontap_poll_job.yaml
  override:
    name: track_<operation>_job
    config:
      url: "https://{{ env.ONTAP_HOST }}/api/cluster/jobs/{{ steps.<trigger_step>.body.job.uuid }}?fields=state,message&return_timeout=120"
      poll:
        interval_seconds: 5
```

## Common API Categories

### Storage

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/storage/volumes` | GET | List volumes |
| `/api/storage/volumes` | POST | Create a volume (async) |
| `/api/storage/volumes/{uuid}` | GET | Get volume details |
| `/api/storage/volumes/{uuid}` | PATCH | Update volume (async) |
| `/api/storage/volumes/{uuid}` | DELETE | Delete volume (async) |
| `/api/storage/volumes/{uuid}/snapshots` | POST | Create snapshot (async) |
| `/api/storage/aggregates` | GET | List aggregates |

### Cluster

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/cluster` | GET | Cluster info (name, version) |
| `/api/cluster/nodes` | GET | List nodes |
| `/api/cluster/jobs/{uuid}` | GET | Poll async job status |

### Networking & Protocols

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/protocols/nfs/export-policies` | GET/POST | NFS export policies |
| `/api/protocols/nfs/export-policies/{id}/rules` | POST | Add export rule |
| `/api/protocols/cifs/shares` | GET/POST | CIFS/SMB shares |
| `/api/protocols/cifs/shares/{svm-uuid}/{share}/acls/{user}/{type}` | PATCH | Set share ACL |

### SVM

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/svm/svms` | GET | List SVMs |
| `/api/svm/svms/{uuid}` | GET | Get SVM details |

## Standard Env Variables

Every ONTAP workflow uses at minimum:

| Variable | Purpose | Default |
|----------|---------|---------|
| `ONTAP_HOST` | Cluster management IP or hostname | `""` (required) |
| `ONTAP_USER` | Admin username | `"admin"` |
| `ONTAP_PASS` | Admin password | `""` (required) |
| `SVM_NAME` | Storage virtual machine | `"vs0"` |

Additional variables depend on the operation (e.g. `VOLUME_NAME`, `AGGR_NAME`, `VOLUME_SIZE`).

## Timeouts

| Operation | Recommended `timeout` | Notes |
|-----------|----------------------|-------|
| Simple GET | 30s | Default |
| POST/PATCH (sync) | 60s | Volume create, snapshot |
| Discovery (many fields) | 150s | Node discovery with all fields |
| `return_timeout` query param | 30–120s | Server-side wait before async return |

## Retry Guidance

| Scenario | `attempts` | `delay_seconds` |
|----------|-----------|-----------------|
| Standard GET | 1 (no retry) | — |
| Network-dependent discovery | 3 | 30 |
| Flaky endpoints | 3 | 5 |
