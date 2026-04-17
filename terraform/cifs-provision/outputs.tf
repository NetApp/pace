output "volume_name" {
  description = "Name of the created volume"
  value       = netapp-ontap_volume.cifs_vol.name
}

output "mount_path" {
  description = "NAS junction path for the volume"
  value       = netapp-ontap_volume.cifs_vol.nas.junction_path
}

output "share_name" {
  description = "Name of the CIFS share"
  value       = netapp-ontap_cifs_share.cifs_share.name
}

output "share_path" {
  description = "Path the CIFS share points to"
  value       = netapp-ontap_cifs_share.cifs_share.path
}
