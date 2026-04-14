# ONTAP REST API Patterns

Canonical reference for ONTAP REST API conventions used across all automation
examples in this repository (Python, Ansible, and Terraform).
For the full API specification, see the
[ONTAP REST API documentation](https://docs.netapp.com/us-en/ontap-restapi/swagger-ui/index.html).

## Base URL

All ONTAP REST endpoints follow this pattern:

```
https://<cluster-management-ip-or-hostname>/api/<category>/<resource>
```

## Authentication

| Field | Value | Notes |
|-------|-------|-------|
| `username` | Admin user | Basic auth — typically `admin` |
| `password` | Admin password | Never hardcode; use env vars or vault |
| `verify_ssl` | `false` | Required for lab / self-signed certs |

## Standard Headers

| Header | Value | When |
|--------|-------|------|
| `Accept` | `application/hal+json` | All requests |
| `Content-Type` | `application/json` | POST and PATCH requests |

## Query Parameters

| Parameter | Usage | Example |
|-----------|-------|---------|
| `fields` | Select which fields to return | `?fields=name,uuid,space` |
| `name` | Filter by name | `?name=vol1` |
| `svm.name` | Filter by SVM | `?svm.name=vs0` |
| `return_timeout` | Server-side wait (seconds) before returning | `&return_timeout=30` |
| `max_records` | Limit number of returned records | `&max_records=100` |

Combine with `&`: `?name=vol1&svm.name=vs0&fields=name,uuid&return_timeout=30`

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

Key fields: `records[].uuid`, `records[].name`, `num_records`.

### Single Resource (GET by UUID)

Returned when fetching a specific resource by its UUID.

```json
{
  "uuid": "abc-123",
  "name": "cluster1",
  "version": { "full": "9.14.1", "generation": 9, "major": 14, "minor": 1 }
}
```

Key fields: `name`, `version.full` (nested via dot notation).

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

Key field: `job.uuid` — used to construct the poll URL.

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

## Async Job Flow

Any POST or PATCH that triggers a long-running operation returns a `job` object.
The standard pattern is:

1. **Trigger** — POST/PATCH returns `{ "job": { "uuid": "..." } }`
2. **Poll** — GET `/api/cluster/jobs/{uuid}?fields=state,message&return_timeout=120` until `state != running`
3. **Continue** — use the poll result's `state` and `message` in downstream logic

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
