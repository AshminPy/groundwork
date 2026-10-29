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
}

resource "aws_sqs_queue" "jobs" {
  name                      = "reports-jobs-${var.environment}"
  message_retention_seconds = 345600
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/reports/worker/${var.environment}"
  retention_in_days = 14
}

variable "environment" {
  type = string
}
