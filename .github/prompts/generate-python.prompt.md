---
description: "Generate a Python script that automates an ONTAP storage task using REST APIs"
---

# Generate ONTAP Python Workflow

You are generating a Python script for the **pace** repository.
The script automates a NetApp ONTAP storage task using exclusively REST APIs.

## Task

{task description}

## Reference Files

Use these repository files as the authoritative source for conventions:

- [python/ontap_client.py](../../python/ontap_client.py) - shared REST client (MUST import and use this)
- [python/nfs_provision.py](../../python/nfs_provision.py) - reference implementation pattern
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - API endpoints, auth, async jobs
- [docs/example-template/python/example.py](../../docs/example-template/python/example.py) - skeleton to start from
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - naming, CI, quality bar

## Step 1 - Clarify Inputs

Before writing code, identify what information is missing and ask me.
Common inputs: SVM name, volume name/size, aggregate, protocol details,
cluster hostname, special options (snapshot policy, QoS, junction path).

## Step 2 - API Sequence

List the ONTAP REST API calls in execution order:

| # | Method | Endpoint | Key Body/Query Params | Sync/Async | Why |
|---|--------|----------|-----------------------|------------|-----|

Rules:
- ONTAP REST only - no ZAPI, no CLI passthrough, no SSH.
- Target ONTAP 9.8+ endpoints.
- Full endpoint paths (e.g. `/api/storage/volumes`).
- For async calls, include the poll step: `GET /api/cluster/jobs/{uuid}`.

Wait for my confirmation before generating code.

## Step 3 - Generate Python Script

File: `python/<use_case>.py` (snake_case filename)

### Mandatory conventions

```
#!/usr/bin/env python3
```

- Module docstring with numbered steps, prerequisites (`pip install -r requirements.txt`),
  env vars (`ONTAP_HOST`, `ONTAP_PASS`), and CLI usage.
- `from __future__ import annotations`
- Import the shared client: `from ontap_client import OntapClient`
- Authenticate: `with OntapClient.from_env() as client:`
  - Required env: `ONTAP_HOST`, `ONTAP_PASS`
  - Optional env: `ONTAP_USER` (default `admin`), `ONTAP_VERIFY_SSL` (default `false`)
- Operational params via `argparse` with env-var fallbacks:
  ```python
  p.add_argument("--svm", default=os.environ.get("SVM_NAME", "vs0"))
  ```
- HTTP calls through the client:
  ```python
  client.get(path, fields="name,uuid", name=vol_name, **{"svm.name": svm})
  client.post(path, body={...})
  client.patch(path, body={...})
  client.delete(path)
  ```
- Async job polling: `client.poll_job(resp["job"]["uuid"])`
- Logging: `logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")`
  - `logger = logging.getLogger(__name__)` - never use `print()`.
- Entry point:
  ```python
  if __name__ == "__main__":
      try:
          main()
      except KeyboardInterrupt:
          sys.exit(130)
      except Exception:
          logger.exception("<script_name> failed")
          sys.exit(1)
  ```
- Type hints on all functions. No hardcoded credentials.

## Step 4 - Validate

After the code, provide:
1. Exact shell commands to run the script.
2. Error scenarios and how the script handles each.
3. Teardown / cleanup instructions.

## Copyright header (required)

Every generated source file MUST start with the standard NetApp header in the
language-appropriate comment syntax. The `insert-license` pre-commit hook
will add it automatically, but include it from the start so AI-generated
output passes review on first read.

```text
© 2026 NetApp, Inc. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
See the NOTICE file in the repo root for trademark and attribution details.
```

Place after any shebang (`#!/usr/bin/env python3`), YAML directive (`---`),
or `<!DOCTYPE html>` line. Do **not** duplicate the full trademark text in
source files - it lives in [NOTICE](../../NOTICE) and the LICENSE appendix.
