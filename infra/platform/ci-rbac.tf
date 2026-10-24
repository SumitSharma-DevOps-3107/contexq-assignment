# EKS access entries in infra/ci map the two CodeBuild roles to these groups.
resource "kubernetes_cluster_role_v1" "ci_plan" {
  metadata { name = "ray-ci-plan-reader" }
  rule {
    api_groups     = [""]
    resources      = ["namespaces"]
    resource_names = ["ray-assignment"]
    verbs          = ["get"]
  }
  rule {
    api_groups     = ["rbac.authorization.k8s.io"]
    resources      = ["clusterroles", "clusterrolebindings"]
    resource_names = ["ray-cluster-autoscaler", "ray-ci-plan-reader"]
    verbs          = ["get"]
  }
}
resource "kubernetes_cluster_role_binding_v1" "ci_plan" {
  metadata { name = "ray-ci-plan-reader" }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.ci_plan.metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = "ray-ci-plan"
    api_group = "rbac.authorization.k8s.io"
  }
}
resource "kubernetes_role_v1" "ci_plan" {
  for_each = toset(["ray-assignment", "kube-system"])
  metadata {
    name      = "ray-ci-plan-reader"
    namespace = each.key
  }
  rule {
    api_groups = ["", "apps", "rbac.authorization.k8s.io"]
    resources  = concat(["serviceaccounts", "deployments", "roles", "rolebindings", "configmaps"], each.key == "ray-assignment" ? ["secrets", "services"] : [])
    verbs      = ["get", "list"]
  }
  depends_on = [kubernetes_namespace_v1.ray]
}
resource "kubernetes_role_binding_v1" "ci_plan" {
  for_each = kubernetes_role_v1.ci_plan
  metadata {
    name      = "ray-ci-plan-reader"
    namespace = each.key
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = each.value.metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = "ray-ci-plan"
    api_group = "rbac.authorization.k8s.io"
  }
}
resource "kubernetes_role_v1" "ci_deploy" {
  metadata {
    name      = "ray-ci-deployer"
    namespace = kubernetes_namespace_v1.ray.metadata[0].name
  }
  rule {
    api_groups = ["ray.io"]
    resources  = ["rayjobs"]
    verbs      = ["create", "get", "list", "delete"]
  }
  rule {
    api_groups = [""]
    resources  = ["pods", "pods/log"]
    verbs      = ["get", "list"]
  }
}
resource "kubernetes_role_binding_v1" "ci_deploy" {
  metadata {
    name      = "ray-ci-deployer"
    namespace = kubernetes_namespace_v1.ray.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.ci_deploy.metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = "ray-ci-deploy"
    api_group = "rbac.authorization.k8s.io"
  }
}
