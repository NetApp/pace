# Python Script Examples

Plain Python scripts that automate ONTAP workflows using the REST API with the
`requests` library. Each script is self-contained and designed to be copied,
adapted, and used in production.

For ONTAP REST API conventions (endpoints, auth, headers, async jobs), see the
[ONTAP API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Ansible or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

---

## Prerequisites

- Python 3.11+
- Network access to an ONTAP cluster management LIF (HTTPS)
- Cluster admin credentials (or appropriate RBAC user)

## Setup

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

All scripts read connection details from environment variables:

```bash
export ONTAP_HOST=10.0.0.1       # cluster management LIF
export ONTAP_USER=admin           # default: admin
export ONTAP_PASS=your_password
```

Or use an env file:

```bash
# cluster.env
ONTAP_HOST=10.0.0.1
ONTAP_USER=admin
ONTAP_PASS=your_password
```

```bash
set -a && source cluster.env && set +a
```

> SSL verification is disabled by default for lab environments with
> self-signed certificates. Set `ONTAP_VERIFY_SSL=true` for production.

---

## Examples

### Cluster Info

Retrieve the cluster version and list all nodes with serial numbers.

```bash
python cluster_info.py
```

### NFS Volume Provisioning

Create a FlexVol volume, set up an NFS export policy with a client rule, and
assign the policy to the volume.

```bash
python nfs_provision.py \
    --svm vs0 \
    --volume vol_nfs_test_01 \
    --size 100MB \
    --aggregate aggr1 \
    --client-match 10.0.0.0/8
```

All flags can also be set via environment variables (`SVM_NAME`, `VOLUME_NAME`,
`VOLUME_SIZE`, `AGGR_NAME`, `CLIENT_MATCH`).

---

## File Overview

| File | Purpose |
|---|---|
| `ontap_client.py` | Reusable ONTAP REST client (session management, auth, polling, error handling) |
| `cluster_info.py` | Get cluster version + node list |
| `nfs_provision.py` | Create NFS volume with export policy |
| `requirements.txt` | Python dependencies |

## Code Patterns

These scripts demonstrate several patterns you can reuse:

- **`OntapClient.from_env()`** — builds a configured client from environment
  variables so credentials never appear in code
- **`client.poll_job(uuid)`** — polls an async ONTAP job until completion with
  configurable interval and timeout
- **Context manager** — `with OntapClient.from_env() as client:` ensures the
  HTTP session is properly closed
- **Structured logging** — all output goes through `logging`, not `print()`,
  so you can control verbosity and format
