variable "project_id" {
  type        = string
  description = "The GCP project ID where the Artifact Registry repository is created."
}

variable "location" {
  type        = string
  description = "The regional location for the Artifact Registry repository."
}

variable "repository_id" {
  type        = string
  description = "The Artifact Registry repository ID."
}

variable "description" {
  type        = string
  description = "The description for the Artifact Registry repository."
  default     = ""
}

variable "format" {
  type        = string
  description = "The package format for the Artifact Registry repository."
  default     = "DOCKER"
}
