---
description: "Generate a Terraform module that automates a NetApp storage task using REST APIs"
---
<!-- Generated from ai/ontap/generate-terraform.md by scripts/generate_ai_assets.py. Do not edit; run `make ai-assets`. -->

# Generate Terraform Storage Module

You are generating a Terraform module for the **pace** repository.
The module provisions NetApp ONTAP storage resources via the `NetApp/netapp-ontap`
provider, which calls exclusively REST APIs.

## Task

{task description}

## Reference Files

Use these repository files as the authoritative source for conventions:

- [terraform/ontap/nfs-provision/main.tf](../../terraform/ontap/nfs-provision/main.tf) - reference implementation
- [terraform/ontap/nfs-provision/variables.tf](../../terraform/ontap/nfs-provision/variables.tf) - variable patterns
- [terraform/ontap/nfs-provision/outputs.tf](../../terraform/ontap/nfs-provision/outputs.tf) - output patterns
- [terraform/ontap/nfs-provision/terraform.tfvars.example](../../terraform/ontap/nfs-provision/terraform.tfvars.example) - tfvars template
- [docs/example-template/terraform/](../../docs/example-template/terraform/) - skeleton files
- [docs/ontap-api-patterns.md](../../docs/ontap-api-patterns.md) - API endpoints and conventions
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - naming, CI, quality bar

## Step 1 - Clarify Inputs

Before writing HCL, identify what information is missing and ask me.
Common inputs: SVM name, volume name/size, aggregate, protocol details,
cluster hostname, special options (snapshot policy, QoS, junction path).

## Step 2 - API Sequence & Resource Mapping

List the REST API calls the provider makes and map each to a Terraform
resource or data source:

| # | REST Endpoint | Terraform Resource/Data | Key Attributes | Why |
|---|---------------|-------------------------|----------------|-----|

Rules:
- The provider calls ONTAP REST APIs internally.
- Target ONTAP 9.8+.
- Provider: `NetApp/netapp-ontap`, version `~> 2.5`.
- Terraform `required_version >= 1.4`.
- Use `depends_on` where resource ordering matters.

Wait for my confirmation before generating HCL.

## Step 3 - Generate Module

Directory: `terraform/<product>/<use-case>/` (kebab-case directory name)

Create four files:

### main.tf

```hcl
# <use-case> - Brief description.

terraform {
  required_version = ">= 1.4"
  required_providers {
    netapp-ontap = {
      source  = "NetApp/netapp-ontap"
      version = "~> 2.5"
    }
  }
}

provider "netapp-ontap" {
  connection_profiles = [
    {
      name           = "cluster1"
      hostname       = var.ontap_host
      username       = var.ontap_username
      password       = var.ontap_password
      validate_certs = var.validate_certs
    },
  ]
}
```

- Every resource/data: `cx_profile_name = "cluster1"`.
- Use `depends_on` blocks where ordering is required.

### variables.tf

- Every variable needs `description` and `type`.
- Passwords: `sensitive = true`.
- Sensible defaults where appropriate (e.g. `username = "admin"`).
- Standard variables to always include:
  `ontap_host`, `ontap_username`, `ontap_password`, `validate_certs`,
  `svm_name`, plus use-case-specific variables.

### outputs.tf

- Meaningful outputs with `description` (e.g. volume UUID, share path).

### terraform.tfvars.example

- Placeholder values with comments. Never include real credentials.

## Step 4 - Validate

After the module, provide:
1. Exact commands: `terraform init`, `terraform plan`, `terraform apply`.
2. Drift detection behavior.
3. `terraform destroy` instructions for cleanup.

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
