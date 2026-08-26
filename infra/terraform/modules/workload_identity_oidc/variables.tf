variable "project_id" {
  type        = string
  description = "The GCP project ID where the workload identity pool is created."
}

variable "pool_id" {
  type        = string
  description = "The workload identity pool ID."
}

variable "provider_id" {
  type        = string
  description = "The workload identity pool provider ID."
}

variable "issuer_uri" {
  type        = string
  description = "The OIDC issuer URI of the identity provider."
}

variable "attribute_mapping" {
  type        = map(string)
  description = "CEL expressions that map IdP claims to Google STS attributes."
}

variable "attribute_condition" {
  type        = string
  description = "CEL expression that must be true for a token to be accepted."
}

variable "allowed_audiences" {
  type        = list(string)
  description = "Accepted JWT aud values. Empty uses the provider default audience only."
  default     = []
}

variable "pool_display_name" {
  type        = string
  description = "Display name for the workload identity pool."
  default     = ""
}

variable "provider_display_name" {
  type        = string
  description = "Display name for the OIDC provider."
  default     = ""
}

variable "description" {
  type        = string
  description = "Description applied to the pool and provider."
  default     = ""
}
