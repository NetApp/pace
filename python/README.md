# Python Script Examples

Plain Python scripts that automate NetApp storage workflows over REST using the
`requests` library. Each script is self-contained and designed to be copied
and adapted for your environment.

For REST API conventions used by these examples (endpoints, auth, headers,
async jobs), see the
[Platform API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Ansible or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

> **Note:** These scripts are runnable illustrations. Unit tests live in
> `Unit_tests/` and can be run with `pytest Unit_tests/`. CI validates lint
> and formatting via Ruff in addition to running the test suite.

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

All scripts read connection details from environment variables.

> **Important:** The values below are placeholders for illustration only.
> Replace `ONTAP_HOST`, `ONTAP_USER`, and `ONTAP_PASS` with your actual
> cluster details before running any script.

```bash
export ONTAP_HOST=10.0.0.1       # cluster management LIF
export ONTAP_USER=admin           # default: admin
export ONTAP_PASS=your_password
```

Or use an env file and pass it to scripts that support `--env-file`:

```bash
# cluster.env
ONTAP_HOST=10.0.0.1
ONTAP_USER=admin
ONTAP_PASS=your_password
```

```bash
# Linux / macOS
set -a && source cluster.env && set +a

# Windows PowerShell
Get-Content cluster.env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim()) }
}
```

Scripts that accept `--env-file` (e.g. `cluster_setup_basic.py`) can also load
the file directly:

```bash
python cluster_setup_basic.py --env-file cluster.env
```

> SSL verification is disabled by default to support environments that use
> self-signed certificates. We recommend setting `ONTAP_VERIFY_SSL=true`
> once CA-signed certificates are in place.

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
| `cluster_setup_basic.py` | Create a new ONTAP cluster from two pre-cluster nodes |
| `nfs_provision.py` | Create NFS volume with export policy |
| `cifs_provision.py` | Create CIFS/SMB share (optionally create CIFS server) |
| `snapmirror_provision_src_managed.py` | Provision a SnapMirror relationship from the source cluster |
| `snapmirror_provision_dest_managed.py` | Provision a SnapMirror relationship from the destination cluster |
| `snapmirror_test_failover.py` | Create a FlexClone of the SnapMirror destination for test failover |
| `snapmirror_cleanup_test_failover.py` | Delete the FlexClone created by a test failover |
| `requirements.txt` | Python dependencies |

## Code Patterns

These scripts demonstrate several patterns you can reuse:

- **`OntapClient.from_env()`** - builds a configured client from environment
  variables so credentials never appear in code
- **`client.poll_job(uuid)`** - polls an async ONTAP job until completion;
  accepts keyword args `interval` (seconds between polls, default 5) and
  `timeout` (max seconds to wait, default 300); raises `RuntimeError` on
  job failure and `TimeoutError` on timeout
- **`client.wait_snapmirrored(rel_uuid)`** - polls a SnapMirror relationship
  until its state reaches `snapmirrored`; accepts `interval` and `max_wait`
- **`client.update_auth(username, password)`** - replaces session credentials
  mid-workflow (used by `cluster_setup_basic.py` after cluster creation)
- **Context manager** - `with OntapClient.from_env() as client:` ensures the
  HTTP session is properly closed
- **Structured logging** - all output goes through `logging`, not `print()`,
  so you can control verbosity and format

## Adapting for Your Environment

These scripts illustrate workflows using simple API call sequences. When
adapting them, consider adding the following based on your requirements:

- **Idempotency** - check whether a resource exists before creating it
  (e.g. `GET /storage/volumes?name=vol01&svm.name=vs0` before calling
  `POST /storage/volumes`). Ansible modules handle this natively; Python
  and Terraform scripts require explicit checks or state tracking.
- **Retry and backoff** - handle transient network or API errors gracefully
- **Partial failure recovery** - clean up or resume when a multi-step workflow
  fails midway
- **Dry-run mode** - log intended actions without executing them
- **Input validation** - enforce constraints on volume sizes, naming
  conventions, or CIDR ranges before calling the API
