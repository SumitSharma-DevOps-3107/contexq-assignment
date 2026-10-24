# AWS deployment layers

Target: the configured assignment account, Singapore (`ap-southeast-1`). Local authentication:
`ray-assignment-login` (browser login) -> `ray-assignment` (credential process)
-> `ray-assignment-role` (assumes the user's existing provisioning role).
Terraform creates separate, scoped workload roles; the provisioning role is never
attached to Ray pods or worker nodes.

1. `bootstrap`: encrypted/versioned state bucket; local bootstrap state must be
   retained securely. All other layers use separate S3 keys and native S3 locking.
2. `data`: encrypted/private data bucket, Glue database, immutable ECR repository,
   and an account-wide $30 gross monthly budget, excluding credits/refunds.
3. `compute`: two-AZ VPC, private nodes, one NAT, free S3 gateway endpoint, EKS
   1.34 standard support, one On-Demand ARM system node, 0–2 Spot ARM workers,
   OIDC and scoped IRSA roles, eight-hour compute lease guard.
4. `platform`: KubeRay, workload service account, and AWS Cluster Autoscaler.
   Ray's autoscaler adjusts pods; Cluster Autoscaler adjusts only the worker ASG.
5. `ci`: GitHub OIDC roles and ephemeral private CodeBuild projects. See
   `docs/cicd.md` for workflow setup, budget checks and CI teardown order.

## Configuration and execution

Create an ignored `.env.aws.local` containing `export` assignments for
`AWS_PROFILE`, `AWS_REGION`, `EXPECTED_AWS_ACCOUNT_ID` and
`AWS_PROVISIONING_ROLE_NAME`. Use identifiers only; credentials stay in AWS CLI's
login/keychain storage. Do not commit this file.

```sh
source scripts/aws-env.sh
# Optional: export BUDGET_ALERT_EMAIL=your-address
.venv/bin/python scripts/aws-configure-project.py
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan -out=bootstrap.tfplan
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

For `data`, then `compute`, then `platform`, run `init -backend-config=backend.hcl`,
`plan -out=<layer>.tfplan`, review the plan, and `apply <layer>.tfplan`. Do not run
platform until EKS and nodes are ready. Plans and generated settings are ignored
by Git. Explicit account checks prevent applying to another account. Configure
your current public `/32` IP before connecting; the API server's private endpoint
serves worker traffic, while its public endpoint accepts only that IP.

The eight-hour deadline starts when configuration is generated, not when a job
starts. Regenerating settings preserves an existing deadline; only an explicit
`LEASE_EXPIRES_AT` UTC value overrides it. Check total spending before opening a
new window. Terraform rejects expired deadlines or deadlines more than eight
hours away. The Lambda guard is installed before EKS creation and
checks every 15 minutes. On expiry it requests deletion of **only this project's**
two nodegroups, EKS cluster, NAT gateway, and associated Elastic IP. It retains
S3/Glue/ECR/state and logs. Deletion is asynchronous and can fail; this is a
fallback, not a hard billing cap or a replacement for normal Terraform teardown.

## Pipeline

Build and push the Linux ARM64 image to the ECR URL from `terraform output` in
the data layer, using a unique tag. Generate the datasets with `make data` and
upload the two CSVs to `s3://<data-bucket>/input/`. Set `RAY_IMAGE` to the ECR tag
or digest, then run `.venv/bin/python scripts/render-aws-job.py`.

Use a dedicated EKS kubeconfig/context (never the kind context), then create the
rendered job. The driver and workers receive IRSA tokens; no static AWS keys are
rendered. Successful reports include their assumed-role ARNs. The Glue database
is managed by Terraform; the application manages only `registry` table metadata
and data under `warehouse/`. Models/reports go under `artifacts/<run-id>/`.

```sh
export RAY_IMAGE=<repository-url>@sha256:<pushed-image-digest>
bash scripts/aws-submit.sh
kubectl --kubeconfig runtime/eks-kubeconfig -n ray-assignment get rayjobs,pods
```

The submission helper checks the account and requires at least 30 minutes of
remaining compute lease. It uses a separate kubeconfig and never changes the
local kind context. Re-running the configuration generator retains the existing
budget alert email unless `BUDGET_ALERT_EMAIL` explicitly overrides it.

## Teardown

Destroy `platform` first while the Kubernetes endpoint is reachable, then
`compute`. Confirm no EKS nodes, NAT gateways, or allocated EIPs remain for the
project. Keep `data` and `bootstrap` until the submission evidence is backed up.
Data buckets and ECR intentionally refuse deletion while nonempty. Do not empty
the remote-state bucket before destroying the stacks that use it.

If the lease guard already deleted EKS, remove only the now-nonexistent platform
resources from its state after reviewing `terraform state list`; then destroy
compute to reconcile remaining networking/IAM/logging resources. Never target
unrelated account resources for cleanup.

## Boundaries

This is a short-lived demonstration: one system node and one NAT are deliberate
cost compromises, not an HA production topology. Spot interruption resilience
uses bounded Ray retries and idempotent Iceberg commits; recovery still needs a
cloud failure test. No automatic On-Demand worker fallback is enabled. There is
no LoadBalancer service or public Ray dashboard. Central workload logs and full
Prometheus monitoring remain a later milestone.
