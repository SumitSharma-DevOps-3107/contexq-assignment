# EKS module

Reusable private EKS foundation for the Ray assignment. Module release candidate
1.0.0; see CHANGELOG.md. Local consumers are versioned by the repository commit.
Publish a reviewed Git tag before advertising a remote release; pin remote module
sources to the reviewed immutable commit rather than a branch. Terraform's
`version` argument applies to registry modules, not local or Git sources.

## Usage

```hcl
module "eks" {
  source              = "../modules/eks"
  name                = "ray-assignment"
  subnet_ids          = module.network.private_subnets
  admin_principal_arn = var.admin_principal_arn
  kubernetes_version  = "1.34"
  system_pool = {
    instance_types = ["m6g.large"]
    min_size = 1
    desired_size = 1
    max_size = 1
  }
  workers_pool = {
    instance_types = ["m6g.large", "m7g.large"]
    min_size = 0
    desired_size = 1
    max_size = 2
  }
  enable_demo_ssm = false
}
```

## Contract and design

- Terraform >= 1.10 and < 2.0; AWS provider >= 6.70 and < 7.0.
  The caller pins its tested provider exactly and commits `.terraform.lock.hcl`.
  This module has no backend or provider configuration; the caller owns both.
- Required inputs: name, private subnet IDs in at least two AZs, explicit
  Kubernetes version and stable administrator IAM ARN. Distinct subnet IDs are
  validated; the caller must verify AZ distribution and private routing.
- Defaults: On-Demand ARM64 system pool, diversified ARM64 Spot worker pool,
  encrypted 20 GiB gp3 disks, IMDSv2 with hop limit one, private-only endpoint,
  rotated KMS key, explicit administrator access and separate CNI IRSA.
- Pool size ordering and whole-number constraints are validated. Instance types
  must support the ARM64 AMI; callers own compatibility and quotas. This module
  intentionally does not claim x86/GPU portability without a matching AMI change.
- Mandatory assignment-pool labels and workload=ray worker taint preserve actor
  isolation. Dynamic blocks implement additional taints and instance/volume tags.
  Locals centralize tagging and the OIDC issuer. Fixed resources keep stable state
  addresses for the original system/worker pools; no state moves are required.
- Worker desired size is owned by Cluster Autoscaler after initial creation.
  System pool desired size remains Terraform-managed. The module creates node
  pools; the platform layer installs the autoscaler, KubeRay and observability.
- Control-plane log types and retention are configurable; audit/authenticator
  logs cannot be omitted. Standard support is selected; verify the AWS support
  calendar before deploying any pinned Kubernetes version.
- Outputs retain the existing contract: cluster name/ARN/endpoint/CA/security
  group, OIDC ARN/URL, worker ASG names, nodegroup ARNs and cluster KMS key ARN.
- SSM is off by default. Opt-in grants only node registration and Session Manager
  channel actions on the shared node role (these actions require wildcard
  resources). Operator StartSession rights are separate; no inbound SSH rule or
  static credential is created. All nodes share this role, so the opt-in affects
  both pools. Use a dedicated operator host/role for long-lived production access.

## Validation and lifecycle

Run `terraform fmt -check -recursive infra`, `terraform -chdir=infra/compute validate`,
`python scripts/security-scan.py`, and a reviewed caller plan. Never apply a plan
with unexpected replacements. Cloud evidence must distinguish source validation
from an executed deployment. This release candidate is not an HA certification.

The caller owns VPC/NAT, workload IRSA, budget and lease cleanup. Destroy platform
before compute. Preserve storage KMS keys while encrypted objects exist. The
cluster key has a 30-day deletion window. For production, size the system pool
for availability, extend log retention, pin validated addon/AMI versions, and add
upgrade, backup and disaster-recovery procedures. One system node is a deliberate
budget-limited demonstration default.
