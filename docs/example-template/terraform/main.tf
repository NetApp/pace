# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

terraform {
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
      name     = "cluster"
      hostname = var.ontap_hostname
      username = var.ontap_username
      password = var.ontap_password
      validate_certs = var.ontap_validate_certs
    }
  ]
}

# Add data sources or resources below
# data "netapp-ontap_cluster" "cluster" {
#   cx_profile_name = "cluster"
# }
