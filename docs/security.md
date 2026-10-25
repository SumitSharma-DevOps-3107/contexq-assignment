# Security controls and outstanding findings

These controls reduce risk; this assignment is not yet production-ready. GitHub
Actions uses read-only repository permissions for PR checks and no AWS identity.
The cloud planner now runs only manually from protected main; its live AWS OIDC
trust no longer accepts pull_request subjects. Terraform changes still require a
reviewed deployment process; no workflow automatically applies Terraform.

## Merge policy

Main requires one independent approving review, fresh approval after changes,
approval of the most recent push by someone other than its pusher, CODEOWNER
review where a base-branch owner exists, resolved conversations, an up-to-date
branch, and successful GitHub Actions checks `validate`, `security`, `pr-title`.
Administrators are included; force pushes and deletion are disabled. The applied
policy is recorded in `security/branch-protection.json`. Settings administrators
can still change repository policy; this is not a complete Zero Trust architecture.

The owner will add a peer with write access. Add that peer to CODEOWNERS alongside
the owner before merging owner-authored changes once CODEOWNERS is on main.
GitHub reads CODEOWNERS from the base branch; adoption of this file still requires
the independently enforced peer approval. Authors cannot self-approve. No bypass
was granted. CODEOWNERS also protects security tooling and workflows through review.

## Local checks

Install once from the project root:

```sh
python3 scripts/install-security-tools.py
.venv/bin/pip install pre-commit==4.3.0
.venv/bin/pre-commit install --hook-type pre-commit --hook-type commit-msg
.venv/bin/pre-commit run --all-files
```

This is `.pre-commit-config.yaml`, not a `.gitcommit` file. Staged changes are
scanned with Gitleaks, Terraform formatting is checked, Terraform security is
scanned with Trivy, and commit messages must use Conventional Commits. Hooks do
not rewrite source. Findings include remediation and reference links; formatting
can be fixed with `terraform fmt -recursive infra`. Scanners are version- and
SHA256-pinned for macOS ARM, Linux ARM and Linux x64 in `security/tools.lock.json`.
Local hooks can be skipped by a developer; independent required CI is the merge
enforcement boundary. No AWS resources are needed for these checks.

Example title: `security(ci): enforce reviewed deployments` (maximum 72 chars).
GitHub PR title checks also run when a title is edited. Workflow values are passed
through environment variables, not interpolated into executable shell text.

## Terraform and plan scanning

Trivy scans HCL on every PR; HIGH and CRITICAL findings fail the required check.
Gitleaks scans git history with redacted output. Private CodeBuild also saves each
Terraform plan in a temporary directory, converts it with `terraform show -json`,
and scans the resolved plan. Binary plans and JSON are deleted on exit and never
uploaded as public artifacts. Only check ID, severity, title, remediation and
reference URL are published; resource values, source snippets and resource names
are excluded. Missing/invalid scanner results fail closed. Private textual plan
output retains the existing short-lived S3 access controls.

On 2026-10-25, HCL scanning found these five distinct checks. The required security
check intentionally remains failing until remediation or a separately reviewed,
resource-scoped exception is justified. No broad suppression is configured.

| Check | Finding and next action |
|---|---|
| AWS-0039 | Scanner cannot infer EKS default envelope encryption. EKS 1.28+ already encrypts Kubernetes API data using an AWS-owned KMS key. Verify the cluster version and document a scoped exception, or implement customer-managed KMS if required. This finding does **not** prove secrets were unencrypted. |
| AWS-0040 | Public EKS API access is enabled for local administration. Move administration to private connectivity, then disable the public endpoint. |
| AWS-0041 | Source scan cannot resolve private admin CIDRs; the root module already requires /32 addresses. Verify resolved plan CIDRs before deciding whether a scoped false-positive exception is appropriate. Do not replace /32 restrictions with 0.0.0.0/0. |
| AWS-0132 | S3 uses AES256 SSE-S3, not customer-managed KMS. Implement key policies and matching IRSA/planner permissions before changing encryption; account for KMS charges and historical objects. |
| AWS-0104 | CodeBuild has TCP 443 egress to all destinations. Introduce controlled artifact/package egress or a proxy and private AWS endpoints, then restrict destinations; allow for endpoint cost. |

Saved private pre-apply compute/data plan JSON was also scanned successfully as a
format/integration check and produced blocking findings. Unknown pre-apply bucket
IDs can cause additional public-access association findings; those are not evidence
that live buckets were public. A fresh cloud plan was not run after the compute
lease expired. Do not recreate paid infrastructure merely to make CI green.

The existing image also fails the golden promotion gate (10 CRITICAL, 48 HIGH in
the recorded ECR scan). Rebuild from a patched base, update vulnerable packages,
then rescan before promotion; see `golden-images.md`. Passing basic ECR OS scanning
alone does not establish application dependency or runtime security.

Sources: [Trivy Terraform scanning](https://trivy.dev/docs/latest/tutorials/misconfiguration/terraform/),
[EKS default envelope encryption](https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html),
[GitHub required reviews](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews).

## Validation and rollback

36 tests pass, including missing/stale scan rejection, title validation and plan
summary redaction. Actionlint and Terraform formatting pass. Gitleaks found no
secrets in the existing history. HCL and saved-plan scans correctly block known
findings. Required review remains pending a second collaborator.

For a defective control, open a reviewed fix or revert PR; do not disable branch
protection to merge it. Restoring PR AWS trust would grant unreviewed code cloud
access and is not a safe rollback. Leave cloud CI paused and preserve the $30
budget until a new bounded demo window is explicitly authorized.
