# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

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
