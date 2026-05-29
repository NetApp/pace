# Ansible Playbook Examples

Ansible playbooks that automate NetApp storage workflows. Each playbook is
self-contained and designed to be copied and adapted for your environment;
today's examples use the
[`netapp.ontap`](https://galaxy.ansible.com/ui/repo/published/netapp/ontap/)
Galaxy collection.

For REST API conventions used by these examples (endpoints, auth, headers,
async jobs), see the
[Platform API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Python or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

> **Catalog:** [`catalog.yaml`](../catalog.yaml) lists every Ansible example with
> prerequisites, inputs, and outputs. Sections below follow the same format.

---

## Prerequisites

- Python 3.11+
- Ansible core 2.15+ (`pip install ansible`)
- Network access to an ONTAP cluster management LIF (HTTPS)
- Cluster admin credentials (or appropriate RBAC user)

## Setup

```bash
cd ansible

# Install the NetApp ONTAP collection from Galaxy
ansible-galaxy collection install -r requirements.yml

# Configure connection variables
cp group_vars/ontap.yml.example group_vars/ontap.yml
# Edit group_vars/ontap.yml with your cluster details
```

Update `inventory/hosts.yml` with your cluster management LIF:

```yaml
all:
  children:
    ontap:
      hosts:
        cluster1:
          ontap_hostname: 10.0.0.1   # <-- your cluster IP
```

## Configuration

Connection settings live in `group_vars/ontap.yml`. At minimum, set:

```yaml
ontap_hostname: "{{ inventory_hostname }}"
ontap_username: admin
ontap_password: your_password
ontap_https: true
ontap_validate_certs: false   # supports self-signed certs; set true once CA-signed certs are in place
```

For production, encrypt the file with Ansible Vault:

```bash
ansible-vault encrypt group_vars/ontap.yml
ansible-playbook -i inventory/hosts.yml cluster_info.yml --ask-vault-pass
```

---

## Examples

### Cluster Info

**Use case:** `cluster-info` | **Status:** verified | **ONTAP:** 9.8+

Retrieve the cluster version and list all nodes with serial numbers.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, `group_vars/ontap.yml`, `inventory/hosts.yml`

**Usage:**

```bash
ansible-playbook -i inventory/hosts.yml cluster_info.yml
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| _(none)_ | | | Connection via `group_vars/ontap.yml` |

| Output | Description |
|--------|-------------|
| cluster_version | Cluster ONTAP version (debug output) |
| nodes | Node names and serial numbers (debug output) |

### NFS Volume Provisioning

**Use case:** `nfs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create a FlexVol volume, set up an NFS export policy with a client rule, and assign the policy to the volume.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, `group_vars/ontap.yml`, `inventory/hosts.yml`

**Usage:**

```bash
ansible-playbook -i inventory/hosts.yml nfs_provision.yml
```

Override variables on the command line:

```bash
ansible-playbook -i inventory/hosts.yml nfs_provision.yml \
    -e volume_name=vol_nfs_demo \
    -e volume_size=200 \
    -e aggregate_name=aggr1 \
    -e client_match=10.0.0.0/8
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| svm_name | no | vs0 | Target SVM |
| volume_name | no | vol_nfs_test_01 | FlexVol name |
| volume_size | no | 100 | Volume size |
| volume_size_unit | no | mb | Size unit |
| aggregate_name | yes | aggr1 | Target aggregate |
| client_match | no | 0.0.0.0/0 | NFS export client CIDR |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name |
| mount_path | NAS junction path |
| export_policy | Dedicated export policy name |

### CIFS Share Provisioning

**Use case:** `cifs-provision` | **Status:** verified | **ONTAP:** 9.8+

Create a FlexVol volume with NTFS security style, a CIFS share, and share ACL.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, `group_vars/ontap.yml`, CIFS enabled on the SVM

**Usage:**

```bash
ansible-playbook -i inventory/hosts.yml cifs_provision.yml \
    -e volume_name=cifs_test_env
```

Override variables on the command line:

```bash
ansible-playbook -i inventory/hosts.yml cifs_provision.yml \
    -e volume_name=cifs_demo \
    -e share_name=demo_share \
    -e aggregate_name=aggr1 \
    -e acl_user=Everyone \
    -e acl_permission=full_control
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| svm_name | no | vs0 | Target SVM |
| volume_name | yes | — | FlexVol name |
| volume_size | no | 100 | Volume size |
| volume_size_unit | no | mb | Size unit |
| aggregate_name | yes | aggr1 | Target aggregate |
| share_name | no | cifs_share_test | CIFS share name |
| share_comment | no | Provisioned by Pace | Share description |
| acl_user | no | Everyone | ACL user or group |
| acl_permission | no | full_control | ACL permission level |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name |
| share_name | CIFS share name |
| mount_path | NAS junction path |

### Cluster Setup

**Use case:** `cluster-setup` | **Status:** verified | **ONTAP:** 9.8+

Create a storage cluster from two pre-cluster nodes.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, pre-cluster node in `inventory/hosts.yml`, cluster network details as extra vars

**Usage:**

```bash
ansible-playbook -i inventory/hosts.yml cluster_setup.yml \
    -e cluster_name=mycluster \
    -e cluster_pass=secret \
    -e cluster_mgmt_ip=10.x.x.x \
    -e cluster_netmask=255.255.192.0 \
    -e cluster_gateway=10.x.x.1 \
    -e partner_mgmt_ip=10.x.x.y
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
| cluster_name | Created cluster name |
| job_status | Cluster-create job result |

### SnapMirror Provision (Source-Managed)

**Use case:** `snapmirror-provision-src` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship from the source-managed view.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, cluster/SVM peering, source RW volume, SnapMirror license on both clusters

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x SOURCE_USER=admin SOURCE_PASS=secret
export SOURCE_SVM=vs0 SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y DEST_USER=admin DEST_PASS=secret DEST_SVM=vs1
ansible-playbook snapmirror_provision_src_managed.yml
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_svm | yes | — | Source SVM name |
| source_volume | yes | — | Source RW volume name |
| dest_svm | yes | — | Destination SVM name |
| sm_policy | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID |
| relationship_state | Final relationship state |
| relationship_healthy | Health status |

### SnapMirror Provision (Destination-Managed)

**Use case:** `snapmirror-provision-dest` | **Status:** verified | **ONTAP:** 9.8+

Provision a SnapMirror relationship with all API calls driven from the destination cluster.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, cluster/SVM peering, source RW volume, SnapMirror license on both clusters

**Usage:**

```bash
export SOURCE_HOST=10.x.x.x SOURCE_USER=admin SOURCE_PASS=secret
export SOURCE_SVM=vs0 SOURCE_VOLUME=vol_rw_01
export DEST_HOST=10.y.y.y DEST_USER=admin DEST_PASS=secret DEST_SVM=vs1
ansible-playbook snapmirror_provision_dest_managed.yml
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_svm | yes | — | Source SVM name |
| source_volume | yes | — | Source RW volume name |
| dest_svm | yes | — | Destination SVM name |
| sm_policy | no | Asynchronous | SnapMirror policy name |

| Output | Description |
|--------|-------------|
| relationship_uuid | SnapMirror relationship UUID |
| relationship_state | Final relationship state |
| relationship_healthy | Health status |

### SnapMirror Test Failover

**Use case:** `snapmirror-test-failover` | **Status:** verified | **ONTAP:** 9.8+

Create a writable FlexClone of a SnapMirror destination volume for test failover.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, healthy SnapMirror relationship in `snapmirrored` state

**Usage:**

```bash
export CLUSTER_A=10.x.x.x CLUSTER_B=10.y.y.y
export DEST_USER=admin DEST_PASS=secret
export SOURCE_VOLUME=*
ansible-playbook snapmirror_test_failover.yml
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_volume | no | `*` | Source volume name, or `*` to auto-detect |

| Output | Description |
|--------|-------------|
| clone_volume | Writable FlexClone volume name |
| relationship_uuid | SnapMirror relationship UUID |
| relationship_state | Post-failover relationship state |

### SnapMirror Cleanup Test Failover

**Use case:** `snapmirror-cleanup-failover` | **Status:** verified | **ONTAP:** 9.8+

Delete the FlexClone created by `snapmirror_test_failover.yml`.

**Prerequisites:** `ansible-galaxy collection install -r requirements.yml`, test failover clone must exist

**Usage:**

```bash
export CLUSTER_A=10.x.x.x CLUSTER_B=10.y.y.y
export DEST_USER=admin DEST_PASS=secret
export SOURCE_VOLUME=vol_rw_01 SOURCE_SVM=vs0
ansible-playbook snapmirror_cleanup_test_failover.yml
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| source_volume | yes | — | Source volume name used to locate the clone |
| source_svm | yes | vs0 | Source SVM name |

| Output | Description |
|--------|-------------|
| clone_deleted | Confirmation that the tagged clone was removed |

---

## File Overview

| File | Purpose |
|---|---|
| `requirements.yml` | Ansible Galaxy collection dependency (`netapp.ontap`) |
| `inventory/hosts.yml` | Sample inventory with an `ontap` host group |
| `group_vars/ontap.yml.example` | Connection and default variable template |
| `cluster_info.yml` | Get cluster version + node list |
| `nfs_provision.yml` | Create NFS volume with export policy |
| `cifs_provision.yml` | Create CIFS share with volume and ACL |
| `cluster_setup.yml` | Create cluster from two pre-cluster nodes |
| `snapmirror_provision_src_managed.yml` | SnapMirror provision (source-managed view) |
| `snapmirror_provision_dest_managed.yml` | SnapMirror provision (destination-managed view) |
| `snapmirror_test_failover.yml` | SnapMirror test failover via FlexClone |
| `snapmirror_cleanup_test_failover.yml` | Clean up test failover clone |

## Design Decisions

- **FQCNs everywhere** - all modules use fully qualified collection names
  (e.g., `netapp.ontap.na_ontap_volume`, not `na_ontap_volume`) per Ansible
  best practices
- **`use_rest: always`** - forces the REST API transport; avoids falling back
  to ZAPI on older collections
- **`wait_for_completion: true`** - the `na_ontap_volume` module handles job
  polling internally, unlike the Python scripts where polling is manual
- **`connection: local`** - ONTAP modules connect over HTTPS from the control
  node; no SSH to the cluster
- **`no_log: false`** - explicitly set so reviewers can verify no task
  accidentally hides output; flip to `true` on tasks that echo credentials
  in production
