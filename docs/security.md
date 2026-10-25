# Security controls and current limitations

The repository stays public on GitHub Free. At the owner's request independent
peer review is paused; it is **not** a completed or enforced control today.
Required GitHub Actions checks `validate`, `security`, and `pr-title`, up-to-date
branches, resolved conversations, and administrator enforcement remain enabled.
Force pushes and deletion remain disabled. CODEOWNERS documents ownership. The
full review-enabled policy is preserved in
`security/branch-protection-with-review.json`; restoration is documented in
`local-grafana.md`. No GitHub subscription or ALB was purchased.

## Shift-left and CI controls

```sh
python3 scripts/install-security-tools.py
.venv/bin/pip install pre-commit==4.3.0
.venv/bin/pre-commit install --hook-type pre-commit --hook-type commit-msg
.venv/bin/pre-commit run --all-files
```

`.pre-commit-config.yaml` checks staged secrets using Gitleaks, Terraform formatting
and security, and Conventional Commit messages. Findings include fixes and reference
links; hooks do not rewrite code. Fix formatting with `terraform fmt -recursive infra`.
Local hooks can be skipped by a developer; required CI independently repeats the
security checks. Scanner binaries are version- and SHA256-pinned. Example title:
`security(ci): enforce reviewed deployments` (maximum 72 characters).

PR checks use read-only repository permissions and no AWS identity. Live cloud
planner OIDC trust accepts protected main only, and cloud CI stays paused. No PR
workflow can obtain the old pull_request-subject role. Cloud plans run manually
from main; no pipeline automatically applies Terraform.

## Terraform remediation and exception

Trivy HCL scanning now passes. EKS's API is private-only with explicit KMS
configuration; S3 uses customer-managed keys with scoped IRSA/CI permissions.
These source changes are **not applied to AWS**; the prior compute lease expired.
See `security-migration.md` for backend-key migration, operator private-connectivity
prerequisites, key-retention requirements and staged validation.

One owner-authorized exception remains: AWS-0104 for the existing CI runner's
TCP 443 outbound rule. It is tied to the exact resource and source hash, expires
2026-11-01 UTC, and checks resolved plan ports/no-ingress before matching. It does
not waive other resources or findings. Independent review of the exception is
pending because review was paused. It must be replaced with destination filtering
before production; an inbound ALB is not an egress control.

Private CodeBuild saves plans in temporary directories, converts them with
`terraform show -json`, and scans them before reporting success. Plan files are
never public artifacts. Summaries omit paths, names, code snippets and resolved
values; only check IDs, severity, titles, fixes and reference URLs are published.
Missing results and scanner errors fail closed. HCL checks explicitly exclude
stale ignored binary plans; fresh resolved JSON plans have their own scan path.

## Container and validation status

41 tests pass, including exception expiry, changed plan ports/ingress, invalid
commit titles, missing/stale image scans, and sanitized plan summaries. All five
Terraform stacks validate; formatting, Actionlint and Helm lint pass. The local
Grafana dashboard, authenticated datasource access and anonymous rejection were
verified; see `docs/evidence/local-grafana-validation.json`.

A new digest-pinned Python 3.11.17/Trixie base builds and runs the local RayJob.
The local Trivy OS/Python scan reports 0 critical and 50 high findings; Java archives
were excluded from this pass. Golden promotion remains blocked, and no new image
was pushed to ECR. See `evidence/patched-image-validation.json`. Fixable findings
include aiohttp, jaraco.context, pyarrow and wheel; remaining OS findings currently
have no fixed version in the scan database. Do not lower the promotion threshold.
The prior ECR image had 10 critical/48 high findings; these are different scans,
not proof of equivalent coverage or a production-ready replacement.

This remains a bounded assignment demonstration, not a complete Zero Trust
architecture. Private-connectivity migration, restricted build destinations,
image remediation, and restored independent review remain production work.

Sources: [Trivy Terraform scanning](https://trivy.dev/docs/latest/tutorials/misconfiguration/terraform/),
[S3 Bucket Key encryption context](https://docs.aws.amazon.com/AmazonS3/latest/userguide/configuring-bucket-key.html),
[GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
