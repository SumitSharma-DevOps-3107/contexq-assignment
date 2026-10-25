terraform {
  backend "s3" {}
}
variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "state_bucket" { type = string }
variable "project" {
  type    = string
  default = "ray-assignment"
}
variable "kubernetes_version" {
  type    = string
  default = "1.34"
  validation {
    condition     = var.kubernetes_version == "1.34"
    error_message = "This tested profile pins Kubernetes 1.34; verify standard-support availability before deploying."
  }
}
variable "admin_principal_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(user|role)/", var.admin_principal_arn))
    error_message = "Use a stable IAM user/role ARN, not an STS session or root ARN."
  }
}
variable "lease_expires_at" {
  type        = string
  description = "UTC RFC3339 deadline for automatic deletion of this demo's EKS compute and NAT."
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform" } }
}
data "aws_partition" "this" {}
data "terraform_remote_state" "data" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = "data/terraform.tfstate", region = var.region }
}
module "network" {
  source = "../modules/network"
  name   = var.project
  region = var.region
}
module "eks" {
  source              = "../modules/eks"
  name                = var.project
  enable_demo_ssm     = var.enable_demo_ssm
  subnet_ids          = module.network.private_subnets
  admin_principal_arn = var.admin_principal_arn
  kubernetes_version  = var.kubernetes_version
  depends_on          = [module.network, aws_cloudwatch_event_target.lease, aws_lambda_permission.lease]
}
locals {
  bucket_arn = data.terraform_remote_state.data.outputs.bucket_arn
  glue_root  = "arn:${data.aws_partition.this.partition}:glue:${var.region}:${var.expected_account_id}"
  database   = data.terraform_remote_state.data.outputs.database
}
module "pipeline_irsa" {
  source          = "../modules/irsa"
  name            = "${var.project}-pipeline"
  oidc_arn        = module.eks.oidc_arn
  oidc_url        = module.eks.oidc_url
  namespace       = "ray-assignment"
  service_account = "ray-pipeline"
  policy_json = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = data.terraform_remote_state.data.outputs.bucket_key_arn, Condition = { StringEquals = {
      "kms:ViaService"                   = "s3.${var.region}.amazonaws.com",
      "kms:EncryptionContext:aws:s3:arn" = local.bucket_arn
    } } },
    { Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = [local.bucket_arn] },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [local.bucket_arn], Condition = { StringLike = {
      "s3:prefix" = ["input", "input/*", "warehouse", "warehouse/*", "artifacts", "artifacts/*"]
    } } },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${local.bucket_arn}/input/*"] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"], Resource = ["${local.bucket_arn}/warehouse/*", "${local.bucket_arn}/artifacts/*"] },
    { Effect = "Allow", Action = ["glue:GetDatabase", "glue:GetTable", "glue:GetTables", "glue:CreateTable", "glue:UpdateTable"], Resource = ["${local.glue_root}:catalog", "${local.glue_root}:database/${local.database}", "${local.glue_root}:table/${local.database}/*"] }
  ] })
}
module "autoscaler_irsa" {
  source          = "../modules/irsa"
  name            = "${var.project}-autoscaler"
  oidc_arn        = module.eks.oidc_arn
  oidc_url        = module.eks.oidc_url
  namespace       = "kube-system"
  service_account = "ray-cluster-autoscaler"
  policy_json = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["autoscaling:DescribeAutoScalingGroups", "autoscaling:DescribeAutoScalingInstances", "autoscaling:DescribeLaunchConfigurations", "autoscaling:DescribeScalingActivities", "autoscaling:DescribeTags", "ec2:DescribeLaunchTemplateVersions", "ec2:DescribeInstanceTypes", "ec2:DescribeImages", "ec2:GetInstanceTypesFromInstanceRequirements", "eks:DescribeNodegroup"], Resource = "*" },
    { Effect = "Allow", Action = ["autoscaling:SetDesiredCapacity", "autoscaling:TerminateInstanceInAutoScalingGroup"], Resource = [for name in module.eks.worker_asg_names : "arn:aws:autoscaling:${var.region}:${var.expected_account_id}:autoScalingGroup:*:autoScalingGroupName/${name}"] }
  ] })
}
output "cluster_name" { value = module.eks.name }
output "endpoint" { value = module.eks.endpoint }
output "ca" { value = module.eks.ca }
output "pipeline_role_arn" { value = module.pipeline_irsa.arn }
output "autoscaler_role_arn" { value = module.autoscaler_irsa.arn }
output "worker_asg_names" { value = module.eks.worker_asg_names }
output "lease_expires_at" { value = var.lease_expires_at }
output "vpc_id" { value = module.network.vpc_id }
output "private_subnets" { value = module.network.private_subnets }
output "cluster_security_group_id" { value = module.eks.security_group_id }

output "cluster_key_arn" { value = module.eks.key_arn }

variable "enable_demo_ssm" {
  type        = bool
  default     = false
  description = "Enable existing node SSM channels for a bounded evidence run."
}
