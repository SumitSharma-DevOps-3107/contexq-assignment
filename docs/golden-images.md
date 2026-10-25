# ECR golden-image promotion

ECR already stores immutable ARM64 application images with scan-on-push and
server-side encryption. The updated release workflow builds a uniquely tagged
`build-<commit>-<run>-<attempt>` candidate, includes BuildKit provenance and SBOM,
and calls `scripts/promote-image.py` before deployment.

The gate checks the exact image digest, resolves the ARM64 executable manifest
when the build produces an OCI index with attestations, and requires a completed
scan less than 24 hours old. Critical, high and undefined-severity findings block
promotion. Pending scans are waited for up to five minutes; missing/failed/stale
results fail closed. A passing image receives an immutable
`golden-<commit>-<run>-<attempt>` tag referencing the same digest; deployment still
uses that digest. No mutable `latest` tag is used.

The current tested image FAILED this new gate: 10 critical and 48 high findings
in the ECR basic scan. It has NOT been promoted to golden. Cloud CI remains paused.
Remediate the base OS packages, rebuild from a reviewed base digest, rerun unit
and application tests, and rescan before deployment. No vulnerability exceptions
or severity threshold reductions were applied. The current working demo image
is evidence of functionality, not an approved production image.

ECR basic scanning is only one control and does not certify the Python supply
chain. Before production add application dependency scanning, signed provenance
verification, a maintained base-image rebuild schedule, policy-based admission,
and approved exception expiry. Pin a verified base digest after remediation;
version tags alone do not guarantee repeatable base contents.

Retention now expires only untagged images after seven days. A candidate and a
golden tag may share one digest: expiring an image selected by its candidate tag
would also remove the golden tag. Therefore retirement of tagged images is
explicit: inspect all tags and running/rollback digest references before deletion.
Storage grows until retired; track ECR storage against the budget and retain a
small, documented rollback set. Do not automate deletion from only a tag prefix.

The deploy role gained only `ecr:DescribeImageScanFindings` for this repository.
Promotion uses its existing scoped `PutImage` permission. This demo does not claim
separation of build and release identities; use a protected release environment
and distinct promotion role for production approval separation.
