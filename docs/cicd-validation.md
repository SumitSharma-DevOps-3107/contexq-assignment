# CI/CD validation — 24 October 2026

The GitHub Actions workflows use repository-scoped OIDC roles in Singapore.
Images build natively on ARM runners. Short-lived CodeBuild jobs reach the private
EKS API for Terraform planning and RayJob deployment. No static AWS keys are stored
in GitHub, and neither workflow applies Terraform or renews the compute lease.

## Verified results

- 21 local tests passed, including budget/lease rejection, digest restrictions,
  and public artifact privacy on success and failure. Actionlint passed.
- [Main-branch plan](https://github.com/SumitSharma-DevOps-3107/contexq-assignment/actions/runs/40110205539): successful plans for all five stacks.
- [Pull-request plan](https://github.com/SumitSharma-DevOps-3107/contexq-assignment/actions/runs/40110528744): successful validation and OIDC plans for all five stacks.
- [Release](https://github.com/SumitSharma-DevOps-3107/contexq-assignment/actions/runs/40110196208): successful ARM image build/push, digest-pinned RayJob execution, sanitized result artifact and job cleanup.

- [Final merged release](https://github.com/SumitSharma-DevOps-3107/contexq-assignment/actions/runs/40110801891): passed on the merged safety/concurrency fixes; RayJob cleanup confirmed.

The compute plan reports changes; a successful plan is not a no-change assertion.
The private output includes a worker minimum-size difference and cleanup-function
archive hash change, with dependent IAM values becoming unknown during planning.
These changes were not applied by CI. Review and reconcile them before any future
owner-run compute apply. Detailed plans stay in private S3 with one-day retention.

The corrected IAM policies scope CodeBuild polling/stopping to project ARNs and
permit budget-tag and Lambda-version reads needed by Terraform. Both main and PR
OIDC subjects use GitHub's immutable repository identity. Cloud jobs now share a
concurrency group to avoid exceeding the one-build capacity; running jobs are not
cancelled by newer submissions.

## Budget and next use

The gross AWS budget is $30, excluding credits/refunds, with email thresholds at
$10, $20 and $25. CI refuses new work at $20 posted spend or with less than 30 minutes
left on the compute lease. Posted billing is delayed and is not a hard spending cap.
The lease expires at 2026-10-24 17:40:01 UTC (23:10 IST); its enabled 15-minute guard
asynchronously removes node groups, EKS, NAT and its EIP. Persistent storage and
other residual resources require the documented teardown.

After validation, `CICD_ENABLED` is set to `false` to avoid unintended cloud runs.
Before another demo, review posted gross spend, reconcile infrastructure and obtain
a new bounded compute window, synchronize private CI configuration, then explicitly
set `CICD_ENABLED=true`. Do not enable it to bypass a failed budget or lease check.

Machine-readable sanitized evidence is in `evidence/cicd-validation-summary.json`.
