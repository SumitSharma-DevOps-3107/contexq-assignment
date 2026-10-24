variable "name" { type = string }
variable "oidc_arn" { type = string }
variable "oidc_url" { type = string }
variable "service_account" { type = string }
variable "namespace" { type = string }
variable "policy_json" { type = string }

resource "aws_iam_role" "this" {
  name = var.name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = var.oidc_arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "${replace(var.oidc_url, "https://", "")}:aud" = "sts.amazonaws.com"
        "${replace(var.oidc_url, "https://", "")}:sub" = "system:serviceaccount:${var.namespace}:${var.service_account}"
      } }
    }]
  })
}
resource "aws_iam_role_policy" "this" {
  role   = aws_iam_role.this.id
  policy = var.policy_json
}
output "arn" { value = aws_iam_role.this.arn }
