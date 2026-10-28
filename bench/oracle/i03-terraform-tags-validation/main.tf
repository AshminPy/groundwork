terraform {
  required_version = ">= 1.6"
}

locals {
  common_tags = {
    owner   = "platform"
    service = "reports"
  }
}

resource "aws_s3_bucket" "reports" {
  bucket = "acme-reports-${var.environment}"
  tags   = merge(local.common_tags, { environment = var.environment })
}

resource "aws_sqs_queue" "jobs" {
  name                      = "reports-jobs-${var.environment}"
  message_retention_seconds = 345600
  tags                      = merge(local.common_tags, { environment = var.environment })
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/reports/worker/${var.environment}"
  retention_in_days = 14
  tags              = merge(local.common_tags, { environment = var.environment })
}

variable "environment" {
  description = "Deployment environment: dev, staging or prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging or prod."
  }
}
