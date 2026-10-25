terraform {
  backend "s3" {}
}
variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "state_bucket" { type = string }
variable "github_repository" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use the exact GitHub owner/repository; wildcards are forbidden."
  }
}
variable "github_oidc_subject_prefix" {
  type        = string
  description = "Exact sub_claim_prefix returned by GitHub's repository OIDC API; preserves immutable IDs."
  validation {
    condition     = can(regex("^repo:[A-Za-z0-9_.-]+(@[0-9]+)?/[A-Za-z0-9_.-]+(@[0-9]+)?$", var.github_oidc_subject_prefix)) && replace(var.github_oidc_subject_prefix, "/@[0-9]+/", "") == "repo:${var.github_repository}"
    error_message = "Use this repository's exact OIDC subject prefix, including immutable IDs when enabled; no wildcards."
  }
}
variable "project" { default = "ray-assignment" }
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform" } }
}
data "terraform_remote_state" "compute" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = "compute/terraform.tfstate", region = var.region }
}
data "terraform_remote_state" "data" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = "data/terraform.tfstate", region = var.region }
}
data "aws_kms_alias" "state" { name = "alias/${var.state_bucket}" }
locals {
  arn         = "arn:aws"
  account     = var.expected_account_id
  state_arn   = "arn:aws:s3:::${var.state_bucket}"
  cluster_arn = "arn:aws:eks:${var.region}:${local.account}:cluster/${var.project}"
  repo_arn    = "arn:aws:ecr:${var.region}:${local.account}:repository/${data.terraform_remote_state.data.outputs.repository_name}"
  tasks       = { plan = 10, deploy = 20 }
}
module "artifacts" {
  source            = "../modules/storage"
  name              = "${var.project}-${local.account}-${var.region}-ci"
  expiring_prefixes = ["source/", "results/"]
}
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
resource "aws_iam_role" "github" {
  for_each             = local.tasks
  name                 = "${var.project}-github-${each.key}"
  max_session_duration = 3600
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
    Action = "sts:AssumeRoleWithWebIdentity"
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
      "token.actions.githubusercontent.com:sub" = ["${var.github_oidc_subject_prefix}:ref:refs/heads/main"]
    } }
  }] })
}
resource "aws_iam_role" "runner" {
  for_each = local.tasks
  name     = "${var.project}-ci-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "codebuild.amazonaws.com" }, Action = "sts:AssumeRole"
    Condition = { StringEquals = { "aws:SourceAccount" = local.account }, ArnEquals = {
      "aws:SourceArn" = "arn:aws:codebuild:${var.region}:${local.account}:project/${var.project}-${each.key}"
    } }
  }] })
}
resource "aws_security_group" "runner" {
  name        = "${var.project}-ci"
  vpc_id      = data.terraform_remote_state.compute.outputs.vpc_id
  description = "Ephemeral CI jobs; HTTPS egress only, no inbound access"
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_vpc_security_group_ingress_rule" "eks" {
  security_group_id            = data.terraform_remote_state.compute.outputs.cluster_security_group_id
  referenced_security_group_id = aws_security_group.runner.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Private API access for ephemeral CI"
}
resource "aws_cloudwatch_log_group" "runner" {
  for_each          = local.tasks
  name              = "/aws/codebuild/${var.project}-${each.key}"
  retention_in_days = 3
}
resource "aws_codebuild_project" "runner" {
  for_each               = local.tasks
  name                   = "${var.project}-${each.key}"
  service_role           = aws_iam_role.runner[each.key].arn
  build_timeout          = each.value
  queued_timeout         = 5
  concurrent_build_limit = 1
  artifacts { type = "NO_ARTIFACTS" }
  source {
    type      = "S3"
    location  = "${module.artifacts.name}/source/${each.key}/bootstrap.zip"
    buildspec = "ci/buildspec-${each.key}.yml"
  }
  environment {
    type            = "ARM_CONTAINER"
    compute_type    = "BUILD_GENERAL1_SMALL"
    image           = "aws/codebuild/amazonlinux-aarch64-standard:3.0"
    privileged_mode = false
    environment_variable {
      name  = "CI_BUCKET"
      value = module.artifacts.name
    }
    environment_variable {
      name  = "EXPECTED_AWS_ACCOUNT_ID"
      value = local.account
    }
    environment_variable {
      name  = "AWS_REGION"
      value = var.region
    }
    environment_variable {
      name  = "CI_MODE"
      value = each.key
    }
  }
  vpc_config {
    vpc_id             = data.terraform_remote_state.compute.outputs.vpc_id
    subnets            = data.terraform_remote_state.compute.outputs.private_subnets
    security_group_ids = [aws_security_group.runner.id]
  }
  logs_config {
    cloudwatch_logs { group_name = aws_cloudwatch_log_group.runner[each.key].name }
  }
  depends_on = [aws_iam_role_policy.runner_base, aws_iam_role_policy.runner_artifact_key, aws_vpc_security_group_ingress_rule.eks]
}
resource "aws_eks_access_entry" "runner" {
  for_each          = local.tasks
  cluster_name      = var.project
  principal_arn     = aws_iam_role.runner[each.key].arn
  kubernetes_groups = ["ray-ci-${each.key}"]
  type              = "STANDARD"
}
resource "aws_iam_role_policy" "github" {
  for_each = local.tasks
  role     = aws_iam_role.github[each.key].id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([
    { Effect = "Allow", Action = ["codebuild:StartBuild"], Resource = aws_codebuild_project.runner[each.key].arn },
    { Effect = "Allow", Action = ["codebuild:BatchGetBuilds", "codebuild:StopBuild"], Resource = aws_codebuild_project.runner[each.key].arn },
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${module.artifacts.arn}/source/${each.key}/*" },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = ["${module.artifacts.arn}/results/${each.key}/*", "${module.artifacts.arn}/config/environment.json"] },
    { Effect = "Allow", Action = ["budgets:ViewBudget"], Resource = "arn:aws:budgets::${local.account}:budget/${var.project}-gross-spend" }
    ], each.key == "deploy" ? [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages", "ecr:DescribeImageScanFindings"], Resource = local.repo_arn }
  ] : []) })
}
resource "aws_iam_role_policy" "runner_base" {
  for_each = local.tasks
  role     = aws_iam_role.runner[each.key].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.runner[each.key].arn}:*" },
    { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:GetBucketAcl"], Resource = module.artifacts.arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = ["${module.artifacts.arn}/source/${each.key}/*", "${module.artifacts.arn}/config/environment.json"] },
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${module.artifacts.arn}/results/${each.key}/*" },
    { Effect = "Allow", Action = ["eks:DescribeCluster"], Resource = local.cluster_arn },
    { Effect = "Allow", Action = ["budgets:ViewBudget"], Resource = "arn:aws:budgets::${local.account}:budget/${var.project}-gross-spend" },
    { Effect = "Allow", Action = ["ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeDhcpOptions", "ec2:DescribeSecurityGroups", "ec2:DescribeSubnets", "ec2:DescribeVpcs"], Resource = "*" },
    { Effect = "Allow", Action = ["ec2:CreateNetworkInterfacePermission"], Resource = "arn:aws:ec2:${var.region}:${local.account}:network-interface/*", Condition = { StringEquals = { "ec2:AuthorizedService" = "codebuild.amazonaws.com" }, ArnEquals = {
      "ec2:Subnet" = [for id in data.terraform_remote_state.compute.outputs.private_subnets : "arn:aws:ec2:${var.region}:${local.account}:subnet/${id}"]
    } } }
  ] })
}
resource "aws_iam_role_policy" "plan_read" {
  role = aws_iam_role.runner["plan"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["budgets:ListTagsForResource"], Resource = "arn:aws:budgets::${local.account}:budget/${var.project}-gross-spend" },
    { Effect = "Allow", Action = ["lambda:ListVersionsByFunction"], Resource = "arn:aws:lambda:${var.region}:${local.account}:function:${var.project}-lease-guard" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [local.state_arn, module.artifacts.arn, data.terraform_remote_state.data.outputs.bucket_arn] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = ["${local.state_arn}/bootstrap/bootstrap-backup.tfstate", "${local.state_arn}/*/terraform.tfstate"] },
    { Effect = "Allow", Action = ["s3:GetBucket*", "s3:GetEncryptionConfiguration", "s3:GetLifecycleConfiguration", "s3:GetAccelerateConfiguration", "s3:GetReplicationConfiguration"], Resource = [local.state_arn, module.artifacts.arn, data.terraform_remote_state.data.outputs.bucket_arn] },
    { Effect = "Allow", Action = ["ec2:Describe*", "eks:Describe*", "eks:List*", "iam:GetRole", "iam:ListRolePolicies", "iam:GetRolePolicy", "iam:ListAttachedRolePolicies", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:GetOpenIDConnectProvider", "iam:ListInstanceProfilesForRole", "lambda:GetFunction*", "lambda:GetPolicy", "lambda:ListTags", "events:DescribeRule", "events:ListTargetsByRule", "events:ListTagsForResource", "logs:DescribeLogGroups", "logs:ListTagsForResource", "ecr:DescribeRepositories", "ecr:GetLifecyclePolicy", "ecr:ListTagsForResource", "glue:GetDatabase", "glue:GetTags", "codebuild:BatchGetProjects"], Resource = "*" }
  ] })
}
output "github_plan_role" { value = aws_iam_role.github["plan"].arn }
output "github_deploy_role" { value = aws_iam_role.github["deploy"].arn }
output "ci_bucket" { value = module.artifacts.name }
output "plan_project" { value = aws_codebuild_project.runner["plan"].name }
output "deploy_project" { value = aws_codebuild_project.runner["deploy"].name }

resource "aws_iam_role_policy" "github_artifact_key" {
  for_each = local.tasks
  role     = aws_iam_role.github[each.key].id
  policy   = local.artifact_key_policy
}
resource "aws_iam_role_policy" "runner_artifact_key" {
  for_each = local.tasks
  role     = aws_iam_role.runner[each.key].id
  policy   = local.artifact_key_policy
}
locals {
  artifact_key_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = module.artifacts.key_arn,
    Condition = { StringEquals = {
      "kms:ViaService"                   = "s3.${var.region}.amazonaws.com",
      "kms:EncryptionContext:aws:s3:arn" = module.artifacts.arn
    } }
  }] })
}
resource "aws_iam_role_policy" "plan_keys" {
  role = aws_iam_role.runner["plan"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = data.aws_kms_alias.state.target_key_arn,
      Condition = { StringEquals = {
        "kms:ViaService"                   = "s3.${var.region}.amazonaws.com",
        "kms:EncryptionContext:aws:s3:arn" = local.state_arn
      } }
    },
    { Effect = "Allow", Action = ["kms:DescribeKey", "kms:GetKeyPolicy", "kms:GetKeyRotationStatus", "kms:ListResourceTags"],
      Resource = [data.aws_kms_alias.state.target_key_arn, module.artifacts.key_arn,
    data.terraform_remote_state.data.outputs.bucket_key_arn, data.terraform_remote_state.compute.outputs.cluster_key_arn] },
    { Effect = "Allow", Action = ["kms:ListAliases"], Resource = "*" }
  ] })
}
