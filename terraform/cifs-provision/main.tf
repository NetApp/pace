# cifs-provision — Create a CIFS (SMB) share with volume and ACL.

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

# Step 1 — Create the FlexVol volume with NTFS security style
resource "netapp-ontap_volume" "cifs_vol" {
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
    junction_path  = "/${var.volume_name}"
    security_style = "ntfs"
  }
}

# Step 2 — Create the CIFS share with ACL on the volume
resource "netapp-ontap_cifs_share" "cifs_share" {
  cx_profile_name = "cluster1"
  name            = var.share_name
  path            = "/${var.volume_name}"
  svm_name        = var.svm_name
  comment         = var.share_comment

  acls = [
    {
      permission    = var.acl_permission
      type          = "windows"
      user_or_group = var.acl_user
    },
  ]

  depends_on = [
    netapp-ontap_volume.cifs_vol,
  ]
}
