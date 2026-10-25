# Prepared Atlantis plan-only profile — not deployed

This is an optional replacement front-end for PR plan requests. It invokes the
existing private CodeBuild planner and posts only each stack's result to the PR.
Full plans remain in private S3. This public repository must not receive raw plans,
state files, private backend settings, account identifiers or sensitive outputs.

The owner requested configuration only: no GitHub App, webhook, load balancer,
volume, server, or Atlantis IAM role has been created. The existing Actions plan
workflow continues to exist; cloud CI remains paused. These YAML files and shell
scripts are checked locally; a live Atlantis startup/webhook test is still needed.

## Controls

- Atlantis v0.48.2, one repository explicitly allowlisted.
- Only `plan`, `version`, `unlock`, and `cancel` commands enabled. Apply is also
  rejected by the server-side workflow. Import/state commands are unavailable.
- No fork PRs, no autoplan, approved/undiverged PR required before a manual plan.
  In a one-person repository a second reviewer is required for this gate; do not
  silently remove it for convenience.
- No repository workflow overrides or custom commands from `atlantis.yaml`.
  Trusted workflow and bridge scripts are baked into the server image, not loaded
  from the PR checkout. Review that image before changing it.
- Private CodeBuild role still has only planning/read access to infrastructure.
  Terraform planning can execute provider/data-source code and read state: run
  only reviewed changes from trusted contributors, even without apply rights.
- Budget and lease checks remain in the bridge. It never renews compute.
- A single StatefulSet with persistent encrypted storage retains locks/checkouts.
  This is not HA. It needs backup/recovery and a separate persistent environment
  before production use; do not attach it to this expiring demo cluster.

## Deployment prerequisites and order

1. Create a GitHub App restricted to this repository with Atlantis's documented
   repository permissions and webhook subscriptions. Keep its private key and
   webhook secret in the platform secret store, never Git or a PR comment.
2. Build from repository root with `docker build -f deploy/atlantis/Dockerfile .`.
   The Dockerfile-specific ignore file excludes local AWS/state files. Scan the
   result, lock the base/package digests for the target platform, push to a
   dedicated ECR repository and deploy by the verified digest. The prepared
   Dockerfile has not been built/published as part of this demo.
3. Provision a dedicated IRSA role trusted only by
   `system:serviceaccount:ray-assignment:atlantis-plan`. Copy the narrowly scoped
   *GitHub plan invoker* permissions from `infra/ci`: start/read/stop only the plan
   CodeBuild project; put only its source prefix; get its result/config prefixes;
   view the one gross budget. Do not grant ECR pushes, deploy project access,
   Terraform state access, or Kubernetes admin rights to the server itself.
4. Supply `atlantis-private-settings` with `AWS_REGION`,
   `EXPECTED_AWS_ACCOUNT_ID`, `CI_BUCKET`, `CODEBUILD_PROJECT`,
   `ATLANTIS_ATLANTIS_URL` and `ATLANTIS_GH_APP_SLUG`. Supply the
   `atlantis-github-app` Secret with `ATLANTIS_GH_APP_ID`,
   `ATLANTIS_GH_APP_INSTALLATION_ID`, and `ATLANTIS_GH_WEBHOOK_SECRET`.
   Mount the PEM key through `atlantis-github-app-key`, key `key.pem`.
5. Replace all deployment placeholders privately, choose an encrypted storage
   class, and deploy in a durable private environment. Provide an HTTPS `/events`
   webhook endpoint with HMAC validation. Protect the UI behind authenticated
   access; restrict network ingress and egress to required endpoints.
6. Open and approve a trusted PR, then comment `atlantis plan -p assignment-plans`.
   Verify the comment contains only per-stack summaries. Confirm `atlantis apply`
   is rejected, fork PRs are rejected, and no write permissions exist in the
   planner. Perform this acceptance test before switching off Actions PR planning.

No binary plan is saved or applied in this design. For a private production repo
that wants complete diffs in comments, explicitly review the disclosure policy
before changing the summary-only bridge. Rollback is to remove the webhook and
server, preserving the existing Actions workflow; do not alter running infrastructure.

Official references: [server flags](https://www.runatlantis.io/docs/server-configuration),
[server-side controls](https://www.runatlantis.io/docs/server-side-repo-config),
[GitHub App setup](https://www.runatlantis.io/docs/access-credentials).
