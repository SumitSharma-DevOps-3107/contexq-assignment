terraform {
  backend "s3" {}
}
variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "project" {
  type    = string
  default = "ray-assignment"
}
variable "budget_alert_email" {
  type     = string
  default  = null
  nullable = true
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform" } }
}
module "data" {
  source = "../modules/storage"
  name   = "${var.project}-${var.expected_account_id}-${var.region}-data"
}
resource "aws_glue_catalog_database" "this" {
  name         = replace(var.project, "-", "_")
  location_uri = "s3://${module.data.name}/warehouse/"
}
resource "aws_ecr_repository" "this" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}
resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = jsonencode({ rules = [{
    rulePriority = 1, description = "Keep the most recent three images"
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 3 }
    action       = { type = "expire" }
  }] })
}
resource "aws_budgets_budget" "account" {
  name         = "${var.project}-gross-spend"
  budget_type  = "COST"
  limit_amount = "30"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  # Account-wide, pre-credit budget also catches untaggable EKS/NAT charges.
  cost_types {
    include_credit = false
    include_refund = false
  }
  dynamic "notification" {
    for_each = var.budget_alert_email == null ? [] : [10, 20, 25]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "ABSOLUTE_VALUE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_alert_email]
    }
  }
}
output "bucket" { value = module.data.name }
output "bucket_arn" { value = module.data.arn }
output "database" { value = aws_glue_catalog_database.this.name }
output "repository_url" { value = aws_ecr_repository.this.repository_url }
output "repository_name" { value = aws_ecr_repository.this.name }
