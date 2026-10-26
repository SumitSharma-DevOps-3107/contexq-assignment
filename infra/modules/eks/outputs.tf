output "name" {
  description = "Name for caller integration."
  value       = aws_eks_cluster.this.name
}
output "arn" {
  description = "Arn for caller integration."
  value       = aws_eks_cluster.this.arn
}
output "endpoint" {
  description = "Endpoint for caller integration."
  value       = aws_eks_cluster.this.endpoint
}
output "security_group_id" {
  description = "Security group id for caller integration."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}
output "ca" {
  description = "Ca for caller integration."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}
output "oidc_arn" {
  description = "Oidc arn for caller integration."
  value       = aws_iam_openid_connect_provider.this.arn
}
output "oidc_url" {
  description = "Oidc url for caller integration."
  value       = aws_iam_openid_connect_provider.this.url
}
output "worker_asg_names" {
  description = "Worker asg names for caller integration."
  value       = aws_eks_node_group.workers.resources[0].autoscaling_groups[*].name
}
output "nodegroup_arns" {
  description = "Nodegroup arns for caller integration."
  value       = [aws_eks_node_group.system.arn, aws_eks_node_group.workers.arn]
}

output "key_arn" {
  description = "Key arn for caller integration."
  value       = aws_kms_key.cluster.arn
}

