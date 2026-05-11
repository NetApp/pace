# Ansible Playbook Examples

Ansible playbooks that automate ONTAP workflows using the
[`netapp.ontap`](https://galaxy.ansible.com/ui/repo/published/netapp/ontap/)
Galaxy collection. Each playbook is self-contained and designed to be copied
and adapted for your environment.

For ONTAP REST API conventions (endpoints, auth, headers, async jobs), see the
[ONTAP API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Python or Terraform, see
[Choosing an approach](../docs/choosing-an-approach.md).

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

Retrieve the cluster version and list all nodes with serial numbers.

```bash
ansible-playbook -i inventory/hosts.yml cluster_info.yml
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

### CIFS Share Provisioning

Create a FlexVol volume with NTFS security style, create a CIFS share, set the
share ACL, and verify the result.

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
