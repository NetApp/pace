variable "ontap_host" {
  description = "ONTAP cluster management LIF hostname or IP"
  type        = string
}

variable "ontap_username" {
  description = "ONTAP admin username"
  type        = string
  default     = "admin"
}

variable "ontap_password" {
  description = "ONTAP admin password"
  type        = string
  sensitive   = true
}

variable "validate_certs" {
  description = "Validate TLS certificates — false to support self-signed certs; set true once CA-signed certs are in place"
  type        = bool
  default     = false
}

variable "svm_name" {
  description = "Storage Virtual Machine (SVM / vserver) name"
  type        = string
  default     = "vs0"
}

variable "volume_name" {
  description = "Name for the new FlexVol volume"
  type        = string
  default     = "vol_cifs_test_01"
}

variable "volume_size" {
  description = "Volume size"
  type        = number
  default     = 100
}

variable "volume_size_unit" {
  description = "Size unit (mb, gb, tb)"
  type        = string
  default     = "mb"
}

variable "aggregate_name" {
  description = "Aggregate to place the volume on"
  type        = string
}

variable "share_name" {
  description = "Name for the CIFS (SMB) share"
  type        = string
  default     = "cifs_share_test"
}

variable "share_comment" {
  description = "Descriptive comment for the CIFS share"
  type        = string
  default     = "Provisioned by orchestrio"
}

variable "acl_user" {
  description = "User or group for the share ACL"
  type        = string
  default     = "Everyone"
}

variable "acl_permission" {
  description = "ACL permission level (read, change, full_control, no_access)"
  type        = string
  default     = "full_control"
}
