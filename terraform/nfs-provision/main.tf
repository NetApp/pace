# nfs-provision — Create an NFS volume with a dedicated export policy.
#
# Equivalent to:  orchestrio run yaml-workflows/workflows/nfs_provision.yaml

terraform {
  required_version = ">= 1.4"

  required_providers {
    netapp-ontap = {
      source  = "NetApp/netapp-ontap"
      version = "~> 1.0"
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

locals {
  export_policy_name = "${var.volume_name}_export_policy"
}

# Step 1 — Create the export policy (before volume so we can reference it)
resource "netapp-ontap_protocols_nfs_export_policy" "vol_policy" {
  cx_profile_name = "cluster1"
  name            = local.export_policy_name
  svm = {
    name = var.svm_name
  }
}

# Step 2 — Add a client-match rule to the policy
resource "netapp-ontap_protocols_nfs_export_policy_rule" "client_rule" {
  cx_profile_name = "cluster1"
  export_policy = {
    name = netapp-ontap_protocols_nfs_export_policy.vol_policy.name
  }
  svm = {
    name = var.svm_name
  }
  clients_match  = var.client_match
  ro_rule        = ["any"]
  rw_rule        = ["any"]
  superuser      = ["any"]
  protocols      = ["nfs"]
}

# Step 3 — Create the FlexVol volume with the export policy assigned
resource "netapp-ontap_storage_volume" "nfs_vol" {
  cx_profile_name = "cluster1"
  name            = var.volume_name
  svm = {
    name = var.svm_name
  }
  aggregates = [
    { name = var.aggregate_name },
  ]
  space = {
    size      = var.volume_size
    size_unit = var.volume_size_unit
  }
  nas = {
    path          = "/${var.volume_name}"
    export_policy = local.export_policy_name
  }

  depends_on = [
    netapp-ontap_protocols_nfs_export_policy_rule.client_rule,
  ]
}
