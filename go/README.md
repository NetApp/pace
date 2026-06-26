# Go Examples

Go programs that automate NetApp storage workflows over REST using the
lightweight `ontapclient` package bundled in this directory. Each program
lives in its own subdirectory and is run with `go run .`.

For REST API conventions used by these examples (endpoints, auth, headers,
async jobs), see the
[Platform API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Python, Ansible, or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

> **Catalog:** [`catalog.yaml`](../catalog.yaml) lists every Go example with
> prerequisites, inputs, and outputs. Sections below follow the same format.

---

## Prerequisites

- Go 1.22+
- Network access to an ONTAP cluster management LIF (HTTPS)
- Cluster admin credentials (or appropriate RBAC user)

## Setup

```bash
cd go
go mod download
```

## Configuration

All programs read connection details from environment variables.

> **Important:** The values below are placeholders for illustration only.
> Replace `ONTAP_HOST`, `ONTAP_USER`, and `ONTAP_PASS` with your actual
> cluster details before running any program.

```bash
export ONTAP_HOST=10.0.0.1       # cluster management LIF
export ONTAP_USER=admin           # default: admin
export ONTAP_PASS=your_password
```

Or use a `.env` file in the `go/` directory (parsed automatically by each program):

```bash
# go/.env
ONTAP_HOST=10.0.0.1
ONTAP_USER=admin
ONTAP_PASS=your_password
```

> SSL verification is disabled by default to support environments that use
> self-signed certificates. Set `ONTAP_VERIFY_SSL=true` once CA-signed
> certificates are in place.

---

## Shared Client — `ontapclient`

All programs import the shared `ontapclient` package located in
`go/ontapclient/`. Never build a new HTTP client in program code.

```go
import ontapclient "github.com/netapp/pace/go/ontapclient"

// From env vars (recommended)
client, err := ontapclient.FromEnv()

// Or explicit
client := ontapclient.New("10.0.0.1", "admin", "secret", false)
defer client.Close()
```

Key methods:

| Method | Description |
|--------|-------------|
| `client.Get(ctx, path, params)` | GET with query params |
| `client.Post(ctx, path, body)` | POST with JSON body |
| `client.Patch(ctx, path, body)` | PATCH with JSON body |
| `client.Delete(ctx, path, body)` | DELETE (optional body) |
| `client.PollJob(ctx, uuid)` | Poll async job until complete |
| `ontapclient.NestedStr(obj, keys...)` | Safe nested string lookup |
| `ontapclient.NestedFloat(obj, keys...)` | Safe nested float lookup |

---

## Examples

### Cluster Info

**Use case:** `cluster-info` | **Status:** verified | **ONTAP:** 9.8+

Retrieve the cluster name, ONTAP version, and a list of all nodes with their
serial numbers.

**Prerequisites:** Go 1.22+, cluster management LIF reachable (HTTPS), cluster
admin credentials

**Usage:**

```bash
export ONTAP_HOST=10.0.0.1  ONTAP_USER=admin  ONTAP_PASS=secret
cd go/cluster_info && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ONTAP_HOST | yes | — | Cluster management LIF |
| ONTAP_USER | no | admin | ONTAP username |
| ONTAP_PASS | yes | — | ONTAP password |

| Output | Description |
|--------|-------------|
| cluster_name | Cluster name (log) |
| cluster_version | ONTAP version string (log) |
| nodes | Node name and serial number for each node (log) |

---

### NFS Provision

**Use case:** `nfs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create an NFS volume with a dedicated export policy and client-match rule.
Idempotent — re-running skips steps already complete.

**Prerequisites:** Go 1.22+, SVM with NFS licensed, online aggregate, cluster
admin credentials

**Usage:**

```bash
export ONTAP_HOST=10.0.0.1  ONTAP_USER=admin  ONTAP_PASS=secret
export SVM_NAME=vs0
export VOLUME_NAME=vol_nfs_test_01
export VOLUME_SIZE=100MB
export AGGR_NAME=aggr1
export CLIENT_MATCH=10.0.0.0/8
cd go/nfs_provision && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ONTAP_HOST | yes | — | Cluster management LIF |
| ONTAP_USER | no | admin | ONTAP username |
| ONTAP_PASS | yes | — | ONTAP password |
| SVM_NAME | yes | — | SVM name |
| VOLUME_NAME | yes | — | Volume name |
| VOLUME_SIZE | no | 100MB | Volume size (e.g. 500MB, 2GB) |
| AGGR_NAME | yes | — | Aggregate name |
| CLIENT_MATCH | no | 0.0.0.0/0 | Export policy client match string |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name (log) |
| mount_path | NFS mount path (log) |
| export_policy | Export policy name (log) |

---

### CIFS Provision

**Use case:** `cifs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create a CIFS (SMB) share with a FlexVol (NTFS security style) and configure
the share ACL. Idempotent — re-running skips steps already complete.
Optionally creates a workgroup CIFS server if none exists on the SVM.

**Prerequisites:** Go 1.22+, SVM with CIFS licensed (or
`CREATE_CIFS_SERVER=true`), online aggregate, cluster admin credentials

**Usage:**

```bash
export ONTAP_HOST=10.0.0.1  ONTAP_USER=admin  ONTAP_PASS=secret
export SVM_NAME=vs1
export VOLUME_NAME=vol_002
export VOLUME_SIZE=100MB
export AGGR_NAME=aggr1
export SHARE_NAME=cifs_share_demo
export ACL_USER=Everyone
export ACL_PERMISSION=full_control
cd go/cifs_provision && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ONTAP_HOST | yes | — | Cluster management LIF |
| ONTAP_USER | no | admin | ONTAP username |
| ONTAP_PASS | yes | — | ONTAP password |
| SVM_NAME | yes | — | SVM name |
| VOLUME_NAME | yes | — | Volume name |
| VOLUME_SIZE | no | 100MB | Volume size (e.g. 500MB, 2GB) |
| AGGR_NAME | yes | — | Aggregate name |
| SHARE_NAME | no | cifs_share_demo | CIFS share name |
| SHARE_COMMENT | no | Provisioned by pace example | Share comment |
| ACL_USER | no | Everyone | ACL user or group |
| ACL_PERMISSION | no | full_control | ACL permission |
| CREATE_CIFS_SERVER | no | false | Set `true` to auto-create a workgroup CIFS server |
| CIFS_SERVER_NAME | no | ONTAP-CIFS | NetBIOS name for new CIFS server |
| CIFS_WORKGROUP | no | WORKGROUP | Workgroup name for new CIFS server |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name (log) |
| share_name | CIFS share name (log) |
| mount_path | Share path (log) |

---

### Cluster Setup

**Use case:** `cluster-setup` | **Status:** verified | **ONTAP:** 9.8+

Create a storage cluster from two pre-cluster nodes.

**Prerequisites:** Go 1.22+, two pre-cluster ONTAP 9 nodes, cluster network details

**Usage:**

```bash
export ONTAP_HOST=10.x.x.x        ONTAP_USER=admin  ONTAP_PASS=
export CLUSTER_NAME=mycluster     CLUSTER_PASS=secret
export CLUSTER_MGMT_IP=10.x.x.x  CLUSTER_NETMASK=255.255.192.0  CLUSTER_GATEWAY=10.x.x.1
export PARTNER_MGMT_IP=10.x.x.y
cd go/cluster_setup_basic && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ONTAP_HOST | yes | — | Node 1 management LIF |
| ONTAP_USER | no | admin | ONTAP username |
| ONTAP_PASS | no | (empty) | Node password (blank on pre-cluster) |
| CLUSTER_NAME | yes | — | New cluster name |
| CLUSTER_PASS | yes | — | Cluster admin password |
| CLUSTER_MGMT_IP | yes | — | Cluster management LIF IP |
| CLUSTER_NETMASK | yes | — | Management subnet mask |
| CLUSTER_GATEWAY | yes | — | Default gateway |
| PARTNER_MGMT_IP | yes | — | Partner node management IP |

| Output | Description |
|--------|-------------|
| cluster_name | Created cluster name (log) |
| job_status | Cluster-create job result (log) |

---

### SnapMirror Provision (Source-Managed)

**Use case:** `snapmirror-provision-src` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship with pre-flight verification on both
clusters; all relationship API calls run on the destination cluster.

**Prerequisites:** Go 1.22+, ONTAP 9.8+ on both clusters, SnapMirror license,
cluster/SVM peering, source RW volume

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x  SOURCE_USER=admin  SOURCE_PASS=secret
export SOURCE_SVM=vs0         SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y     DEST_USER=admin    DEST_PASS=secret
export DEST_SVM=vs1
export SM_POLICY=Asynchronous
cd go/snapmirror_provision_src_managed && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| SOURCE_HOST | yes | — | Source cluster management LIF |
| SOURCE_USER | no | admin | Source cluster username |
| SOURCE_PASS | yes | — | Source cluster password |
| SOURCE_SVM | yes | — | Source SVM name |
| SOURCE_VOLUME | yes | — | Source RW volume name |
| DEST_HOST | yes | — | Destination cluster management LIF |
| DEST_USER | no | admin | Destination cluster username |
| DEST_PASS | yes | — | Destination cluster password |
| DEST_SVM | yes | — | Destination SVM name |
| SM_POLICY | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID (log) |
| relationship_state | Final relationship state (log) |
| relationship_healthy | Health status (log) |

---

### SnapMirror Provision (Destination-Managed)

**Use case:** `snapmirror-provision-dest` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship with all API calls driven from the
destination cluster. Auto-creates cluster peer, SVM peer, and DP volume if
they are missing.

**Prerequisites:** Go 1.22+, ONTAP 9.8+ on both clusters, SnapMirror license,
intercluster LIFs on both clusters, source RW volume

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x  SOURCE_USER=admin  SOURCE_PASS=secret
export SOURCE_SVM=vs0         SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y     DEST_USER=admin    DEST_PASS=secret
export DEST_SVM=vs1
export SM_POLICY=Asynchronous
cd go/snapmirror_provision_dest_managed && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| SOURCE_HOST | yes | — | Source cluster management LIF |
| SOURCE_USER | no | admin | Source cluster username |
| SOURCE_PASS | yes | — | Source cluster password |
| SOURCE_SVM | yes | — | Source SVM name |
| SOURCE_VOLUME | yes | — | Source RW volume name |
| DEST_HOST | yes | — | Destination cluster management LIF |
| DEST_USER | no | admin | Destination cluster username |
| DEST_PASS | yes | — | Destination cluster password |
| DEST_SVM | yes | — | Destination SVM name |
| SM_POLICY | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID (log) |
| relationship_state | Final relationship state (log) |
| relationship_healthy | Health status (log) |

---

### SnapMirror Test Failover

**Use case:** `snapmirror-test-failover` | **Status:** verified | **ONTAP:** 9.8+

Create a writable FlexClone of a SnapMirror destination volume for DR testing
without breaking the replication relationship. Supports auto-detection of
which cluster holds the target DP volume.

**Prerequisites:** Go 1.22+, ONTAP 9.8+ on both clusters, healthy SnapMirror
relationship in `snapmirrored` state with at least one SnapMirror snapshot

**Usage:**

```bash
export CLUSTER_A=10.x.x.x  CLUSTER_B=10.y.y.y
export DEST_USER=admin      DEST_PASS=secret
export SOURCE_VOLUME=vol_rw_01   # or "*" for auto-detection
cd go/snapmirror_test_failover && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| CLUSTER_A | yes | — | First cluster management LIF |
| CLUSTER_B | yes | — | Second cluster management LIF |
| DEST_USER | no | admin | Cluster username (both clusters) |
| DEST_PASS | yes | — | Cluster password |
| SOURCE_VOLUME | no | * | Source volume name (`*` = auto-detect) |

| Output | Description |
|--------|-------------|
| clone_volume | Created FlexClone volume name (log) |
| relationship_uuid | SnapMirror relationship UUID (log) |
| relationship_state | Final relationship state after resync (log) |

---

### SnapMirror Test Failover Cleanup

**Use case:** `snapmirror-cleanup-failover` | **Status:** verified | **ONTAP:** 9.8+

Delete the writable FlexClone created by the test failover workflow.
Only clones tagged by `snapmirror_test_failover` are matched — manually
created volumes are never touched.

**Prerequisites:** Go 1.22+, ONTAP 9.8+ on both clusters,
`snapmirror_test_failover` must have been run first

**Usage:**

```bash
export CLUSTER_A=10.x.x.x  CLUSTER_B=10.y.y.y
export DEST_USER=admin      DEST_PASS=secret
export SOURCE_VOLUME=vol_rw_01
export SOURCE_SVM=vs0
cd go/snapmirror_cleanup_test_failover && go run .
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| CLUSTER_A | yes | — | First cluster management LIF |
| CLUSTER_B | yes | — | Second cluster management LIF |
| DEST_USER | no | admin | Cluster username |
| DEST_PASS | yes | — | Cluster password |
| SOURCE_VOLUME | yes | — | Source volume name used during test failover |
| SOURCE_SVM | yes | — | Source SVM name |

| Output | Description |
|--------|-------------|
| clone_deleted | Confirmation that the clone was deleted (log) |

---

## Conventions

- All programs use `log.Printf` — never `fmt.Print`.
- Environment variables loaded via `loadDotEnv()` helper (reads `go/.env`).
- Required vars checked with `mustEnv()`, optional with `envOrDefault()`.
- Async jobs polled via `client.PollJob(ctx, uuid)`.
- `context.Background()` passed down to every API call for cancellation support.
- No hardcoded credentials — use env vars or a `.env` file.
