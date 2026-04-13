output "volume_name" {
  description = "Name of the created volume"
  value       = netapp-ontap_volume.nfs_vol.name
}

output "mount_path" {
  description = "NAS junction path for mounting"
  value       = netapp-ontap_volume.nfs_vol.nas.junction_path
}

output "export_policy_rule" {
  description = "Export policy rule applied"
  value       = netapp-ontap_nfs_export_policy_rule.client_rule.export_policy_name
}

output "client_match" {
  description = "Client match rule on the export policy"
  value       = var.client_match
}
