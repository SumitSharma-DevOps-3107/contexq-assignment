terraform {
  backend "s3" {}
}
variable "region" { type = string }
variable "expected_account_id" { type = string }
variable "state_bucket" { type = string }
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
}
data "terraform_remote_state" "compute" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = "compute/terraform.tfstate", region = var.region }
}
variable "private_api_proxy_url" {
  type        = string
  default     = null
  description = "Optional local CONNECT proxy to an authenticated SSM tunnel; TLS remains verified."
  validation {
    condition     = var.private_api_proxy_url == null ? true : can(regex("^http://127[.]0[.]0[.]1:[0-9]+$", var.private_api_proxy_url))
    error_message = "The optional demo proxy must bind to IPv4 loopback."
  }
}
provider "kubernetes" {
  proxy_url              = var.private_api_proxy_url
  host                   = data.terraform_remote_state.compute.outputs.endpoint
  cluster_ca_certificate = base64decode(data.terraform_remote_state.compute.outputs.ca)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--region", var.region, "--cluster-name", data.terraform_remote_state.compute.outputs.cluster_name]
  }
}
provider "helm" {
  kubernetes = {
    proxy_url              = var.private_api_proxy_url
    host                   = data.terraform_remote_state.compute.outputs.endpoint
    cluster_ca_certificate = base64decode(data.terraform_remote_state.compute.outputs.ca)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--region", var.region, "--cluster-name", data.terraform_remote_state.compute.outputs.cluster_name]
    }
  }
}
resource "kubernetes_namespace_v1" "ray" {
  metadata { name = "ray-assignment" }
}
resource "kubernetes_service_account_v1" "pipeline" {
  metadata {
    name      = "ray-pipeline"
    namespace = kubernetes_namespace_v1.ray.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn"               = data.terraform_remote_state.compute.outputs.pipeline_role_arn
      "eks.amazonaws.com/sts-regional-endpoints" = "true"
    }
  }
}
resource "helm_release" "kuberay" {
  name       = "kuberay-operator"
  namespace  = kubernetes_namespace_v1.ray.metadata[0].name
  repository = "https://ray-project.github.io/kuberay-helm/"
  chart      = "kuberay-operator"
  version    = "1.5.1"
  wait       = true
  timeout    = 300
  values = [yamlencode({
    watchSingleNamespace = true
    nodeSelector         = { "assignment-pool" = "system" }
    resources            = { requests = { cpu = "100m", memory = "128Mi" }, limits = { cpu = "500m", memory = "256Mi" } }
  })]
}
resource "kubernetes_service_account_v1" "autoscaler" {
  metadata {
    name      = "ray-cluster-autoscaler"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn" = data.terraform_remote_state.compute.outputs.autoscaler_role_arn
    }
  }
}
resource "kubernetes_cluster_role_v1" "autoscaler" {
  metadata { name = "ray-cluster-autoscaler" }
  rule {
    api_groups = [""]
    resources  = ["events", "endpoints"]
    verbs      = ["create", "patch"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods/eviction"]
    verbs      = ["create"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods/status", "nodes"]
    verbs      = ["update"]
  }
  rule {
    api_groups = [""]
    resources  = ["nodes", "pods", "services", "replicationcontrollers", "persistentvolumeclaims", "persistentvolumes", "namespaces"]
    verbs      = ["watch", "list", "get"]
  }
  rule {
    api_groups = ["apps", "extensions"]
    resources  = ["daemonsets", "replicasets", "statefulsets"]
    verbs      = ["watch", "list", "get"]
  }
  rule {
    api_groups = ["policy"]
    resources  = ["poddisruptionbudgets"]
    verbs      = ["watch", "list", "get"]
  }
  rule {
    api_groups = ["storage.k8s.io"]
    resources  = ["storageclasses", "csinodes", "csidrivers", "csistoragecapacities", "volumeattachments"]
    verbs      = ["watch", "list", "get"]
  }
  rule {
    api_groups = ["batch"]
    resources  = ["jobs"]
    verbs      = ["watch", "list", "get"]
  }
  rule {
    api_groups = ["coordination.k8s.io"]
    resources  = ["leases"]
    verbs      = ["create", "get", "update"]
  }
}
resource "kubernetes_cluster_role_binding_v1" "autoscaler" {
  metadata { name = "ray-cluster-autoscaler" }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.autoscaler.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.autoscaler.metadata[0].name
    namespace = "kube-system"
  }
}
resource "kubernetes_role_v1" "autoscaler" {
  metadata {
    name      = "ray-cluster-autoscaler"
    namespace = "kube-system"
  }
  rule {
    api_groups = [""]
    resources  = ["configmaps"]
    verbs      = ["create", "list", "watch"]
  }
  rule {
    api_groups     = [""]
    resources      = ["configmaps"]
    resource_names = ["cluster-autoscaler-status", "cluster-autoscaler-priority-expander"]
    verbs          = ["get", "update", "patch", "delete"]
  }
}
resource "kubernetes_role_binding_v1" "autoscaler" {
  metadata {
    name      = "ray-cluster-autoscaler"
    namespace = "kube-system"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.autoscaler.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.autoscaler.metadata[0].name
    namespace = "kube-system"
  }
}
resource "kubernetes_deployment_v1" "autoscaler" {
  metadata {
    name      = "ray-cluster-autoscaler"
    namespace = "kube-system"
  }
  spec {
    replicas = 1
    selector { match_labels = { app = "ray-cluster-autoscaler" } }
    template {
      metadata { labels = { app = "ray-cluster-autoscaler" } }
      spec {
        service_account_name = kubernetes_service_account_v1.autoscaler.metadata[0].name
        node_selector        = { "assignment-pool" = "system" }
        container {
          name    = "autoscaler"
          image   = "registry.k8s.io/autoscaling/cluster-autoscaler:v1.34.0"
          command = concat(["./cluster-autoscaler", "--cloud-provider=aws", "--stderrthreshold=info", "--v=2", "--scale-down-delay-after-add=2m", "--scale-down-unneeded-time=2m"], [for name in data.terraform_remote_state.compute.outputs.worker_asg_names : "--nodes=0:2:${name}"])
          env {
            name  = "AWS_REGION"
            value = var.region
          }
          resources {
            requests = { cpu = "100m", memory = "256Mi" }
            limits   = { cpu = "500m", memory = "512Mi" }
          }
          security_context {
            run_as_non_root            = true
            run_as_user                = 65534
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
        }
      }
    }
  }
  depends_on = [kubernetes_cluster_role_binding_v1.autoscaler, kubernetes_role_binding_v1.autoscaler]
}
