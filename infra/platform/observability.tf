data "aws_eks_cluster" "observability" {
  name = data.terraform_remote_state.compute.outputs.cluster_name
}
locals {
  observability_issuer = data.aws_eks_cluster.observability.identity[0].oidc[0].issuer
}
resource "aws_cloudwatch_log_group" "ray_pods" {
  name              = "/ray-assignment/pods"
  retention_in_days = 3
  tags              = { Project = "ray-assignment", ManagedBy = "Terraform" }
}
module "logging_irsa" {
  source          = "../modules/irsa"
  name            = "ray-assignment-log-collector"
  oidc_arn        = "arn:aws:iam::${var.expected_account_id}:oidc-provider/${replace(local.observability_issuer, "https://", "")}"
  oidc_url        = local.observability_issuer
  namespace       = kubernetes_namespace_v1.ray.metadata[0].name
  service_account = "ray-log-collector"
  policy_json = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.ray_pods.arn}:log-stream:*" }
  ] })
}
resource "helm_release" "observability" {
  name      = "ray-observability"
  namespace = kubernetes_namespace_v1.ray.metadata[0].name
  chart     = "${path.module}/../../charts/observability"
  wait      = true
  atomic    = true
  timeout   = 300
  values = [yamlencode({
    chartChecksum = sha256(join("", [for file in sort(tolist(fileset("${path.module}/../../charts/observability", "**"))) : filesha256("${path.module}/../../charts/observability/${file}")]))
    logging       = { enabled = true, region = var.region, roleArn = module.logging_irsa.arn, logGroup = aws_cloudwatch_log_group.ray_pods.name }
  })]
  depends_on = [module.logging_irsa]
}
output "ray_log_group" { value = aws_cloudwatch_log_group.ray_pods.name }
