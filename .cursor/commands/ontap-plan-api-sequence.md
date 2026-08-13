<!-- Generated from ai/ontap/plan-api-sequence.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# Plan Storage REST API Sequence

You are an ONTAP REST API specialist. Design the exact sequence of API calls
for a storage operation - **no code yet**, just the API plan.

## Task

{task description}

## Reference

- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - endpoints, auth, query params, async jobs
- ONTAP REST API docs: https://docs.netapp.com/us-en/ontap-restapi/swagger-ui/index.html

## Output Format

For each API call, fill in this table:

| # | Method | Endpoint | Key Body / Query Params | Sync/Async | Idempotent? | Why |
|---|--------|----------|-------------------------|------------|-------------|-----|
| 1 | GET | /api/svm/svms?name=vs0&fields=uuid | - | Sync | Yes | Resolve SVM UUID |

## Rules

1. **REST only** - no ZAPI, no CLI passthrough, no SSH.
2. **ONTAP 9.8+** target minimum.
3. Full endpoint paths (e.g. `/api/storage/volumes`, not just "volumes").
4. For POST/PATCH returning a job, include the poll step:
   `GET /api/cluster/jobs/{uuid}?fields=state,message&return_timeout=120`
5. For collection GETs, specify `fields` and filter params.
6. Note ordering constraints (e.g. "volume must exist before export policy").
7. Mark which steps are idempotent vs not.
8. If multiple approaches exist, list trade-offs briefly.

## Common Endpoint Reference

| Category | Endpoints |
|----------|-----------|
| Storage | `/api/storage/volumes`, `/api/storage/aggregates`, `.../volumes/{uuid}/snapshots` |
| Cluster | `/api/cluster`, `/api/cluster/nodes`, `/api/cluster/jobs/{uuid}` |
| NFS | `/api/protocols/nfs/export-policies`, `.../export-policies/{id}/rules` |
| CIFS | `/api/protocols/cifs/shares`, `.../shares/{svm-uuid}/{share}/acls/{user}/{type}` |
| SVM | `/api/svm/svms`, `/api/svm/svms/{uuid}` |

## Deliverable

After the table, provide:
1. A dependency graph (which calls depend on results of earlier calls).
2. Estimated total API calls for a fresh run vs an idempotent re-run.
3. Potential failure points and recommended retry/fallback strategy.
