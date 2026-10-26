# Security remediation and evidence deployment

EKS now has a private-only API endpoint and an explicit customer-managed KMS key.
All three storage-module buckets (state, data, CI artifacts) use their own rotated
KMS key with S3 Bucket Keys. Scoped pipeline and CI permissions use the exact key
ARN, regional S3 ViaService condition, and bucket ARN encryption context. The
read-only planner can decrypt state and inspect key metadata, but cannot write
state or change keys. Generated backend config explicitly selects the state KMS
key; `encrypt=true` alone could otherwise request SSE-S3.

The original cloud cluster was deleted by its lease. On 25 October the evidence
run applied the state/data storage keys and recreated EKS with a private API and
cluster KMS key. State object encryption and data-bucket defaults were verified.
The CI artifact-key migration and old object/version rewrites remain unvalidated.
Customer-managed keys incur recurring charges when eventually created; retain
state/data keys as long as encrypted objects or versions exist. Do not schedule
key deletion as routine demo compute cleanup.

For a future authorized demo window:

1. Review bootstrap/data plans and the budget. Apply bootstrap first, preserve a
   recoverable local state backup, and confirm the state key output/alias.
2. Regenerate backend settings with `scripts/aws-configure-project.py`; deliberately
   retain the expired lease until a new bounded window is approved. Reconfigure
   existing backends to select the new KMS key. Verify new state writes use SSE-KMS.
3. Apply data before compute so `bucket_key_arn` is available. New defaults do not
   re-encrypt old objects or old versions; any rewrite needs a separate verified
   migration/retention plan. Existing encrypted data must remain recoverable.
4. Create compute only within the new lease. The private EKS API requires an
   operator runner inside the VPC or established VPN/private connectivity for
   platform Terraform, kubectl and Helm. Direct laptop access used by the old
   /32-public-endpoint demo will no longer work. Do not turn public access back on
   just to bypass this prerequisite.
5. Apply CI with its new key permissions; then platform from private connectivity.
   Republish CI settings (including state_key_arn), test decrypt/write permissions
   and fresh resolved-plan scans, and only then consider enabling cloud CI.
6. On rollback retain key access until all dependent encrypted objects/versions
   have been migrated or deliberately retired. Do not revert KMS permissions first.

Temporary egress: `security/egress-exception.json` binds AWS-0104 to the exact CI
security-group source hash, resource address and expiry. Resolved-plan matching
also checks one TCP 443 IPv4 rule and no ingress. Changes to the rule, an unknown
plan value, a different resource/layer or expiry cause failure. This exception is
owner-authorized for the assignment; peer review has been paused, not completed.
It does not allow unrelated findings and is not a production network boundary.

Source scans explicitly select the Terraform HCL scanner so stale ignored binary
plans do not contaminate local results. The private runner separately scans JSON
for each freshly generated plan. Its temporary binary/JSON files remain private.
