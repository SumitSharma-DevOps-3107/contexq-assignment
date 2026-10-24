variable "region" { type = string }
variable "project" {
  type    = string
  default = "ray-assignment"
}
variable "expected_account_id" { type = string }
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform" } }
}
module "state" {
  source = "../modules/storage"
  name   = "${var.project}-${var.expected_account_id}-${var.region}-state"
}
output "state_bucket" { value = module.state.name }
