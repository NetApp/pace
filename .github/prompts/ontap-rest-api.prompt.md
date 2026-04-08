# ONTAP REST API Reference for Orchestrio

Use this prompt for ONTAP REST API context when building workflows, steps, or
debugging. Full spec: https://docs.netapp.com/us-en/ontap-restapi/swagger-ui/index.html
Full reference: `docs/ontap-api-patterns.md`

## Base URL

`https://{{ env.ONTAP_HOST }}/api/<category>/<resource>`

## Auth & Headers (use in `defaults:` block)

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

POST/PATCH steps also need: `Content-Type: "application/json"`

## Standard Env Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ONTAP_HOST` | Cluster management IP/hostname | `""` (required) |
| `ONTAP_USER` | Admin username | `"admin"` |
| `ONTAP_PASS` | Admin password | `""` (required) |
| `SVM_NAME` | Storage virtual machine | `"vs0"` |

## Query Parameters

- `?fields=name,uuid,space` — select return fields
- `?name=X&svm.name=Y` — filter resources
- `&return_timeout=30` — server-side wait (seconds)
- `&max_records=100` — limit results

## Response Shapes

**Collection** (GET list):
```json
{ "records": [{ "uuid": "...", "name": "..." }], "num_records": 2, "_links": {...} }
```
Access: `{{ steps.<name>.body.records.0.uuid }}`, `{{ steps.<name>.body.num_records }}`

**Single resource** (GET by UUID):
```json
{ "uuid": "...", "name": "cluster1", "version": { "full": "9.14.1" } }
```
Access: `{{ steps.<name>.body.name }}`, `{{ steps.<name>.body.version.full }}`

**Async job** (POST/PATCH write ops):
```json
{ "job": { "uuid": "job-uuid-123" } }
```
Access: `{{ steps.<name>.body.job.uuid }}`

**Job poll result** (GET `/api/cluster/jobs/{uuid}`):
```json
{ "state": "success", "message": "Volume created." }
```
States: `queued` | `running` | `success` | `failure`
Access: `{{ steps.<poll_name>.body.state }}`, `{{ steps.<poll_name>.body.message }}`

## Async Job Pattern

POST/PATCH that trigger long-running ops return a job. Poll with:

```yaml
- include: ../steps/ontap_poll_job.yaml
  override:
    name: track_<operation>_job
    config:
      url: "https://{{ env.ONTAP_HOST }}/api/cluster/jobs/{{ steps.<trigger>.body.job.uuid }}?fields=state,message&return_timeout=120"
      poll:
        interval_seconds: 5
```

## Common Endpoints

| Endpoint | Method | Purpose | Async? |
|----------|--------|---------|--------|
| `/api/cluster` | GET | Cluster name, version | No |
| `/api/cluster/nodes` | GET | List nodes | No |
| `/api/cluster/jobs/{uuid}` | GET | Poll job status | No |
| `/api/storage/volumes` | GET | List volumes | No |
| `/api/storage/volumes` | POST | Create volume | Yes |
| `/api/storage/volumes/{uuid}` | PATCH | Update volume | Yes |
| `/api/storage/volumes/{uuid}` | DELETE | Delete volume | Yes |
| `/api/storage/volumes/{uuid}/snapshots` | POST | Create snapshot | Yes |
| `/api/storage/aggregates` | GET | List aggregates | No |
| `/api/svm/svms` | GET | List SVMs | No |
| `/api/protocols/nfs/export-policies` | GET/POST | NFS export policies | No |
| `/api/protocols/nfs/export-policies/{id}/rules` | POST | Add export rule | No |
| `/api/protocols/cifs/shares` | GET/POST | CIFS shares | No |
| `/api/protocols/cifs/shares/{svm-uuid}/{share}/acls/{user}/{type}` | PATCH | Set share ACL | No |

## Timeouts & Retries

| Operation | `timeout` | `retry` |
|-----------|----------|---------|
| Simple GET | 30s | None |
| POST/PATCH | 60s | None |
| Discovery (many fields) | 150s | `attempts: 3, delay_seconds: 30` |
| Flaky endpoints | 30s | `attempts: 3, delay_seconds: 5` |
