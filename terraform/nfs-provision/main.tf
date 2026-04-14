# nfs-provision — Create an NFS volume with a dedicated export policy.

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

# Step 1 — Create the FlexVol volume with NFS enabled
resource "netapp-ontap_volume" "nfs_vol" {
  cx_profile_name = "cluster1"
  name            = var.volume_name
  svm_name        = var.svm_name
  aggregates = [
    { name = var.aggregate_name },
  ]
  space = {
    size      = var.volume_size
    size_unit = var.volume_size_unit
  }
  nas = {
    junction_path = "/${var.volume_name}"
  }
}

# Step 2 — Add a client-match rule to the default export policy
resource "netapp-ontap_nfs_export_policy_rule" "client_rule" {
  cx_profile_name    = "cluster1"
  svm_name           = var.svm_name
  export_policy_name = "default"
  clients_match      = [var.client_match]
  ro_rule            = ["any"]
  rw_rule            = ["any"]
  superuser          = ["any"]
  protocols          = ["nfs"]

  depends_on = [
    netapp-ontap_volume.nfs_vol,
  ]
}
