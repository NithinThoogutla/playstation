variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner of the resources"
  type        = string
  default     = "data-engineering-team"
}

variable "cost_center" {
  description = "Cost center for billing"
  type        = string
  default     = "dataplatform-101"
}

variable "bucket_prefix" {
  description = "Prefix for S3 bucket names to ensure uniqueness"
  type        = string
  default     = "nithin-data-platform"
}

variable "budget_limit" {
  description = "Monthly budget limit in USD"
  type        = string
  default     = "100"
}

variable "budget_alert_email" {
  description = "Email to notify when budget exceeds threshold"
  type        = string
  default     = "sainithin559@gmail.com"
}
