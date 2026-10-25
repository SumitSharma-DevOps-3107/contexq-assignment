locals {
  partition     = split(":", var.admin_principal_arn)[1]
  tags          = merge(var.tags, { Project = var.name, ManagedBy = "Terraform" })
  oidc_issuer   = replace(aws_iam_openid_connect_provider.this.url, "https://", "")
  worker_taints = concat([{ key = "workload", value = "ray", effect = "NO_SCHEDULE" }], var.worker_taints)
}
