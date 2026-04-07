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
  value       = data.netapp-ontap_cluster_nodes.all.cluster_nodes
}
