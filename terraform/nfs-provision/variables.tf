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
  default     = "vol_nfs_test_01"
}

variable "volume_size" {
  description = "Volume size in MB"
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

variable "client_match" {
  description = "Client IP or CIDR for the NFS export policy rule (default 0.0.0.0/0 is for illustration only — restrict to your actual client subnet)"
  type        = string
  default     = "0.0.0.0/0"
}
