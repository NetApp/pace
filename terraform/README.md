# Terraform Examples

Terraform configurations that manage NetApp storage resources. Each module
is self-contained and designed to be copied and adapted for your environment;
today's examples use the
[NetApp ONTAP provider](https://registry.terraform.io/providers/NetApp/netapp-ontap/latest).

For REST API conventions used by these examples (endpoints, auth, headers,
async jobs), see the
[Platform API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Python or Ansible, see
[Choosing an approach](../docs/choosing-an-approach.md).

> **Catalog:** [`catalog.yaml`](../catalog.yaml) lists every Terraform module with
> prerequisites, inputs, and outputs. Sections below follow the same format.

---

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.4
- Network access to an ONTAP cluster management LIF (HTTPS)
- Cluster admin credentials (or appropriate RBAC user)

No manual provider download is needed - `terraform init` fetches the
`NetApp/netapp-ontap` provider automatically.

## Setup

Each use case is a self-contained Terraform root module in its own directory.
The workflow is the same for each:

```bash
cd terraform/cluster-info   # or nfs-provision

# 1. Configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your cluster details

# 2. Initialize (downloads the provider)
terraform init

# 3. Preview changes
terraform plan

# 4. Apply
terraform apply
```

> `terraform.tfvars` contains credentials and is covered by the repo's
> `.gitignore` (`*.tfstate`, `.terraform/`). Never commit it.

---

## Examples

### Cluster Info

**Use case:** `cluster-info` | **Status:** verified | **ONTAP:** 9.8+

Read-only — retrieves the cluster version and lists all nodes. Uses only Terraform data sources, so `terraform apply` makes no changes to the cluster.

**Prerequisites:** Terraform >= 1.4, `cp terraform.tfvars.example terraform.tfvars && terraform init`, cluster credentials in `terraform.tfvars`

**Usage:**

```bash
cd cluster-info
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init && terraform apply
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ontap_host | yes | — | Cluster management LIF |
| ontap_username | no | admin | Admin username |
| ontap_password | yes | — | Admin password |
| validate_certs | no | false | TLS certificate validation |

| Output | Description |
|--------|-------------|
| cluster_name | ONTAP cluster name |
| cluster_version | Full ONTAP software version |
| nodes | List of cluster nodes with serial numbers |

### NFS Volume Provisioning

**Use case:** `nfs-provision` | **Status:** verified | **ONTAP:** 9.8+

Creates a FlexVol volume, a dedicated NFS export policy with a client-match rule, and assigns the policy to the volume.

**Prerequisites:** Terraform >= 1.4, `cp terraform.tfvars.example terraform.tfvars && terraform init`, cluster credentials in `terraform.tfvars`

**Usage:**

```bash
cd nfs-provision
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init && terraform plan
terraform apply
```

To tear down the resources:

```bash
terraform destroy
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ontap_host | yes | — | Cluster management LIF |
| ontap_username | no | admin | Admin username |
| ontap_password | yes | — | Admin password |
| validate_certs | no | false | TLS certificate validation |
| svm_name | no | vs0 | Target SVM |
| volume_name | no | vol_nfs_test_01 | FlexVol name |
| volume_size | no | 100 | Volume size |
| volume_size_unit | no | mb | Size unit |
| aggregate_name | yes | — | Target aggregate |
| client_match | no | 0.0.0.0/0 | NFS export client CIDR |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name |
| mount_path | NAS junction path |
| export_policy | Dedicated export policy name |
| client_match | Export policy client match rule |

### CIFS (SMB) Share Provisioning

**Use case:** `cifs-provision` | **Status:** verified | **ONTAP:** 9.8+

Creates a FlexVol volume with NTFS security style, a CIFS share, and an ACL.

**Prerequisites:** Terraform >= 1.4, `cp terraform.tfvars.example terraform.tfvars && terraform init`, CIFS enabled on the SVM

**Usage:**

```bash
cd cifs-provision
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init && terraform plan
terraform apply
```

To tear down the resources:

```bash
terraform destroy
```

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| ontap_host | yes | — | Cluster management LIF |
| ontap_username | no | admin | Admin username |
| ontap_password | yes | — | Admin password |
| validate_certs | no | false | TLS certificate validation |
| svm_name | no | vs0 | Target SVM |
| volume_name | no | vol_cifs_test_01 | FlexVol name |
| volume_size | no | 100 | Volume size |
| volume_size_unit | no | mb | Size unit |
| aggregate_name | yes | — | Target aggregate |
| share_name | no | cifs_share_test | CIFS share name |
| share_comment | no | Provisioned by Pace | Share description |
| acl_user | no | Everyone | ACL user or group |
| acl_permission | no | full_control | ACL permission level |

| Output | Description |
|--------|-------------|
| volume_name | Created volume name |
| mount_path | NAS junction path |
| share_name | CIFS share name |
| share_path | Path the share points to |

---

## File Overview

```
terraform/
├── README.md                         <- you are here
├── cluster-info/
│   ├── main.tf                       # Provider + data sources
│   ├── variables.tf                  # Input variables
│   ├── outputs.tf                    # Cluster name, version, nodes
│   └── terraform.tfvars.example      # Variable template
├── nfs-provision/
│   ├── main.tf                       # Provider + resources
│   ├── variables.tf                  # Input variables
│   ├── outputs.tf                    # Volume name, mount path, policy
│   └── terraform.tfvars.example      # Variable template
└── cifs-provision/
    ├── main.tf                       # Provider + volume + CIFS share with ACL
    ├── variables.tf                  # Input variables
    ├── outputs.tf                    # Volume name, mount path, share name/path
    └── terraform.tfvars.example      # Variable template
```

## Design Decisions

- **Self-contained root modules** - each directory is independent with its
  own provider block and state. This keeps examples copy-paste-friendly;
  you can grab one directory without pulling the whole repo.
- **`sensitive = true`** on password variables - Terraform redacts these from
  plan/apply output and state display.
- **`depends_on` for ordering** - the NFS module creates the export policy
  and rule before the volume, using explicit `depends_on` to guarantee the
  policy is ready when the volume references it.
- **No remote backend** - examples use the default local backend. Production
  users should configure S3/GCS/Consul for shared state.
- **`terraform.tfvars` over environment variables** - Terraform's native
  variable mechanism; cleaner than `TF_VAR_*` env vars for examples.
