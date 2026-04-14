# Terraform Examples

Terraform configurations that manage ONTAP resources using the
[NetApp ONTAP provider](https://registry.terraform.io/providers/NetApp/netapp-ontap/latest).
Each module is self-contained and designed to be copied and adapted for your
environment.

For ONTAP REST API conventions (endpoints, auth, headers, async jobs), see the
[ONTAP API patterns guide](../docs/ontap-api-patterns.md).
To compare this approach with Python or Ansible, see
[Choosing an approach](../docs/choosing-an-approach.md).

---

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.4
- Network access to an ONTAP cluster management LIF (HTTPS)
- Cluster admin credentials (or appropriate RBAC user)

No manual provider download is needed — `terraform init` fetches the
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

Read-only — retrieves the cluster version and lists all nodes. Uses only
Terraform data sources, so `terraform apply` makes no changes to the cluster.

```bash
cd cluster-info
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init && terraform apply
```

Outputs:

```
cluster_name    = "cluster1"
cluster_version = "9.14.1"
nodes           = [ { name = "node1", serial_number = "..." }, ... ]
```

### NFS Volume Provisioning

Creates a FlexVol volume, a dedicated NFS export policy with a client-match
rule, and assigns the policy to the volume.

```bash
cd nfs-provision
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init && terraform plan   # review the plan
terraform apply                     # create resources
```

To tear down the resources:

```bash
terraform destroy
```

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
└── nfs-provision/
    ├── main.tf                       # Provider + resources
    ├── variables.tf                  # Input variables
    ├── outputs.tf                    # Volume name, mount path, policy
    └── terraform.tfvars.example      # Variable template
```

## Design Decisions

- **Self-contained root modules** — each directory is independent with its
  own provider block and state. This keeps examples copy-paste-friendly;
  you can grab one directory without pulling the whole repo.
- **`sensitive = true`** on password variables — Terraform redacts these from
  plan/apply output and state display.
- **`depends_on` for ordering** — the NFS module creates the export policy
  and rule before the volume, using explicit `depends_on` to guarantee the
  policy is ready when the volume references it.
- **No remote backend** — examples use the default local backend. Production
  users should configure S3/GCS/Consul for shared state.
- **`terraform.tfvars` over environment variables** — Terraform's native
  variable mechanism; cleaner than `TF_VAR_*` env vars for examples.
