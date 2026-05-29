# Python Script Examples

Plain Python scripts that automate NetApp storage workflows over REST using the
`requests` library. Each script is self-contained and designed to be copied
and adapted for your environment.

For REST API conventions used by these examples (endpoints, auth, headers,
async jobs), see the
[Platform API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Ansible or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

> **Catalog:** [`catalog.yaml`](../catalog.yaml) lists every Python example with
> prerequisites, inputs, and outputs. Sections below follow the same format.

> **Note:** These scripts are runnable illustrations, not a tested library.
> There are no unit tests by design - CI validates only lint and formatting
> via Ruff. When you adapt a script for production, add tests appropriate
> to your environment.

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

> SSL verification is disabled by default to support environments that use
> self-signed certificates. We recommend setting `ONTAP_VERIFY_SSL=true`
> once CA-signed certificates are in place.

---

## Examples

### Cluster Info

**Use case:** `cluster-info` | **Status:** verified | **ONTAP:** 9.8+

Retrieve the cluster version and list all nodes with serial numbers.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, `ONTAP_HOST` / `ONTAP_PASS` / `ONTAP_USER`

**Usage:**

```bash
python cluster_info.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| _(none)_ | | | |

| Output | Description |
|--------|-------------|
| cluster_version | Full ONTAP version string (stdout) |
| nodes | Node names and serial numbers (stdout) |

### NFS Volume Provisioning

**Use case:** `nfs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create a FlexVol volume, set up an NFS export policy with a client rule, and assign the policy to the volume.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, `ONTAP_HOST` / `ONTAP_PASS` / `ONTAP_USER`

**Usage:**

```bash
python nfs_provision.py \
    --svm vs0 \
    --volume vol_nfs_test_01 \
    --size 100MB \
    --aggregate aggr1 \
    --client-match 10.0.0.0/8
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| svm | yes | — | Target SVM name |
| volume | yes | — | FlexVol name |
| size | yes | — | Volume size (e.g. `100MB`) |
| aggregate | yes | — | Target aggregate |
| client_match | yes | — | NFS export client CIDR |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name (stdout) |
| mount_path | NAS junction path (stdout) |
| export_policy | Dedicated export policy name (stdout) |

All flags can also be set via environment variables (`SVM_NAME`, `VOLUME_NAME`, `VOLUME_SIZE`, `AGGR_NAME`, `CLIENT_MATCH`).

### CIFS Share Provisioning

**Use case:** `cifs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create a FlexVol volume with NTFS security style, a CIFS share, and share ACL.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, `ONTAP_HOST` / `ONTAP_PASS` / `ONTAP_USER`, CIFS enabled on the SVM

**Usage:**

```bash
python cifs_provision.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| svm | yes | — | Target SVM name |
| volume | yes | — | FlexVol name |
| size | yes | — | Volume size |
| aggregate | yes | — | Target aggregate |
| share_name | yes | — | CIFS share name |
| acl_user | no | Everyone | ACL user or group |
| acl_permission | no | full_control | ACL permission level |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name (stdout) |
| share_name | CIFS share name (stdout) |
| mount_path | NAS junction path (stdout) |

Configure via CLI flags, environment variables, or `--env-file` — see script docstring.

### Cluster Setup

**Use case:** `cluster-setup` | **Status:** verified | **ONTAP:** 9.8+

Create a storage cluster from two pre-cluster nodes.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, pre-cluster node management IP and cluster network details

**Usage:**

```bash
export ONTAP_HOST=10.x.x.x ONTAP_USER=admin ONTAP_PASS=
export CLUSTER_NAME=mycluster CLUSTER_PASS=secret
export CLUSTER_MGMT_IP=10.x.x.x CLUSTER_NETMASK=255.255.192.0
export CLUSTER_GATEWAY=10.x.x.1 PARTNER_MGMT_IP=10.x.x.y
python cluster_setup_basic.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| cluster_name | yes | — | New cluster name |
| cluster_pass | yes | — | Cluster admin password |
| cluster_mgmt_ip | yes | — | Cluster management LIF IP |
| cluster_netmask | yes | — | Management subnet mask |
| cluster_gateway | yes | — | Default gateway |
| partner_mgmt_ip | yes | — | Partner node management IP |

| Output | Description |
|--------|-------------|
| cluster_name | Created cluster name (stdout) |
| job_status | Cluster-create job result (stdout) |

### SnapMirror Provision (Source-Managed)

**Use case:** `snapmirror-provision-src` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship from the source-managed view (API calls run on the destination cluster).

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, cluster/SVM peering, source RW volume, SnapMirror license on both clusters

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x SOURCE_USER=admin SOURCE_PASS=secret
export SOURCE_SVM=vs0 SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y DEST_USER=admin DEST_PASS=secret DEST_SVM=vs1
python snapmirror_provision_src_managed.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_svm | yes | — | Source SVM name |
| source_volume | yes | — | Source RW volume name |
| dest_svm | yes | — | Destination SVM name |
| sm_policy | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID (stdout) |
| relationship_state | Final relationship state (stdout) |
| relationship_healthy | Health status (stdout) |

### SnapMirror Provision (Destination-Managed)

**Use case:** `snapmirror-provision-dest` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship with all API calls driven from the destination cluster.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, cluster/SVM peering, source RW volume, SnapMirror license on both clusters

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x SOURCE_USER=admin SOURCE_PASS=secret
export SOURCE_SVM=vs0 SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y DEST_USER=admin DEST_PASS=secret DEST_SVM=vs1
python snapmirror_provision_dest_managed.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_svm | yes | — | Source SVM name |
| source_volume | yes | — | Source RW volume name |
| dest_svm | yes | — | Destination SVM name |
| sm_policy | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID (stdout) |
| relationship_state | Final relationship state (stdout) |
| relationship_healthy | Health status (stdout) |

### SnapMirror Test Failover

**Use case:** `snapmirror-test-failover` | **Status:** verified | **ONTAP:** 9.8+

Create a writable FlexClone of a SnapMirror destination volume for test failover.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, healthy SnapMirror relationship in `snapmirrored` state

**Usage:**

```bash
export CLUSTER_A=10.x.x.x CLUSTER_B=10.y.y.y
export DEST_USER=admin DEST_PASS=secret
export SOURCE_VOLUME=*
python snapmirror_test_failover.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_volume | no | `*` | Source volume name, or `*` to auto-detect |

| Output | Description |
|--------|-------------|
| clone_volume | Writable FlexClone volume name (stdout) |
| relationship_uuid | SnapMirror relationship UUID (stdout) |
| relationship_state | Post-failover relationship state (stdout) |

### SnapMirror Cleanup Test Failover

**Use case:** `snapmirror-cleanup-failover` | **Status:** verified | **ONTAP:** 9.8+

Delete the FlexClone created by `snapmirror_test_failover.py`.

**Prerequisites:** Python 3.11+, `pip install -r requirements.txt`, test failover clone must exist

**Usage:**

```bash
export CLUSTER_A=10.x.x.x CLUSTER_B=10.y.y.y
export DEST_USER=admin DEST_PASS=secret
export SOURCE_VOLUME=vol_rw_01 SOURCE_SVM=vs0
python snapmirror_cleanup_test_failover.py
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_volume | yes | — | Source volume name used to locate the clone |
| source_svm | yes | vs0 | Source SVM name |

| Output | Description |
|--------|-------------|
| clone_deleted | Confirmation that the tagged clone was removed (stdout) |

---

## File Overview

| File | Purpose |
|---|---|
| `ontap_client.py` | Reusable ONTAP REST client (session management, auth, polling, error handling) |
| `cluster_info.py` | Get cluster version + node list |
| `nfs_provision.py` | Create NFS volume with export policy |
| `cifs_provision.py` | Create CIFS share with volume and ACL |
| `cluster_setup_basic.py` | Create cluster from two pre-cluster nodes |
| `snapmirror_provision_src_managed.py` | SnapMirror provision (source-managed view) |
| `snapmirror_provision_dest_managed.py` | SnapMirror provision (destination-managed view) |
| `snapmirror_test_failover.py` | SnapMirror test failover via FlexClone |
| `snapmirror_cleanup_test_failover.py` | Clean up test failover clone |
| `requirements.txt` | Python dependencies |

## Code Patterns

These scripts demonstrate several patterns you can reuse:

- **`OntapClient.from_env()`** - builds a configured client from environment
  variables so credentials never appear in code
- **`client.poll_job(uuid)`** - polls an async ONTAP job until completion with
  configurable interval and timeout
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
