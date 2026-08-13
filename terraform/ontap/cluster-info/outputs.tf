# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

output "cluster_name" {
  description = "ONTAP cluster name"
  value       = data.netapp-ontap_cluster.info.name
}

output "cluster_version" {
  description = "ONTAP software version"
  value       = data.netapp-ontap_cluster.info.version.full
}

output "nodes" {
  description = "List of cluster nodes"
  value       = data.netapp-ontap_cluster.info.nodes
}
