terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "6.70.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "3.4.0" }
    helm       = { source = "hashicorp/helm", version = "3.3.0" }
  }
}
