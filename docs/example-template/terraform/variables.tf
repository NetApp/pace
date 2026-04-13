variable "ontap_hostname" {
  description = "ONTAP cluster management IP or hostname"
  type        = string
}

variable "ontap_username" {
  description = "Admin username"
  type        = string
  default     = "admin"
}

variable "ontap_password" {
  description = "Admin password"
  type        = string
  sensitive   = true
}

variable "ontap_validate_certs" {
  description = "Validate TLS certificates (set false for self-signed)"
  type        = bool
  default     = false
}
