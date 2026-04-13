# Ansible Playbook Examples

Ansible playbooks that automate ONTAP workflows using the
[`netapp.ontap`](https://galaxy.ansible.com/ui/repo/published/netapp/ontap/)
Galaxy collection. For the equivalent low-code YAML approach, see the
[`yaml-workflows/workflows/`](../yaml-workflows/workflows/) directory.

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
ontap_validate_certs: false   # set true for CA-signed certificates
```

For production, encrypt the file with Ansible Vault:

```bash
ansible-vault encrypt group_vars/ontap.yml
ansible-playbook -i inventory/hosts.yml cluster_info.yml --ask-vault-pass
```

---

## Examples

### Cluster Info

Retrieve the cluster version and list all nodes with serial numbers.

```bash
ansible-playbook -i inventory/hosts.yml cluster_info.yml
```

**Equivalent Orchestrio command:**

```bash
orchestrio run workflows/cluster_info.yaml -E cluster.env
```

### NFS Volume Provisioning

Create a FlexVol volume, set up an NFS export policy with a client rule, and
assign the policy to the volume.

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

**Equivalent Orchestrio command:**

```bash
orchestrio run workflows/nfs_provision.yaml -E cluster.env \
    -e VOLUME_NAME=vol_nfs_demo \
    -e VOLUME_SIZE=200MB \
    -e AGGR_NAME=aggr1
```

---

## File Overview

| File | Purpose |
|---|---|
| `requirements.yml` | Ansible Galaxy collection dependency (`netapp.ontap`) |
| `inventory/hosts.yml` | Sample inventory with an `ontap` host group |
| `group_vars/ontap.yml.example` | Connection and default variable template |
| `cluster_info.yml` | Get cluster version + node list |
| `nfs_provision.yml` | Create NFS volume with export policy |

## Design Decisions

- **FQCNs everywhere** — all modules use fully qualified collection names
  (e.g., `netapp.ontap.na_ontap_volume`, not `na_ontap_volume`) per Ansible
  best practices
- **`use_rest: always`** — forces the REST API transport; avoids falling back
  to ZAPI on older collections
- **`wait_for_completion: true`** — the `na_ontap_volume` module handles job
  polling internally, unlike the Python scripts where polling is manual
- **`connection: local`** — ONTAP modules connect over HTTPS from the control
  node; no SSH to the cluster
- **`no_log: false`** — explicitly set so reviewers can verify no task
  accidentally hides output; flip to `true` on tasks that echo credentials
  in production
