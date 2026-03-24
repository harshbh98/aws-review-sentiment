variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for all resource names"
  type        = string
  default     = "review-sentiment"
}

variable "environment" {
  description = "Deployment environment (dev | staging | prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "language_code" {
  description = "BCP-47 language code passed to Amazon Comprehend"
  type        = string
  default     = "en"
}

variable "force_destroy_buckets" {
  description = "Allow Terraform to delete non-empty S3 buckets (set false for prod)"
  type        = bool
  default     = true
}
