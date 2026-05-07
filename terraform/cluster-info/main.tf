# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

# cluster-info — Retrieve ONTAP cluster version and list all nodes.

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

# Get cluster info version and nodes
data "netapp-ontap_cluster" "info" {
  cx_profile_name = "cluster1"
}
