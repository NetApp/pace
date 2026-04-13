# cluster-info — Retrieve ONTAP cluster version and list all nodes.
#
# Equivalent to:  orchestrio run yaml-workflows/workflows/cluster_info.yaml

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
