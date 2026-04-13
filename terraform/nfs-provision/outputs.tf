output "volume_name" {
  description = "Name of the created volume"
  value       = netapp-ontap_storage_volume.nfs_vol.name
}

output "mount_path" {
  description = "NAS junction path for mounting"
  value       = netapp-ontap_storage_volume.nfs_vol.nas.path
}

output "export_policy" {
  description = "Name of the export policy assigned to the volume"
  value       = netapp-ontap_protocols_nfs_export_policy.vol_policy.name
}

output "client_match" {
  description = "Client match rule on the export policy"
  value       = var.client_match
}
