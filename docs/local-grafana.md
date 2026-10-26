# Local Grafana on GitHub Free and the $30 assignment budget

Run `bash scripts/grafana-local.sh` from the project root after the local kind
cluster is running. It installs Prometheus and Grafana in `kind-ray-assignment`,
creates a random admin password, and opens a port-forward bound only to
127.0.0.1. Open http://127.0.0.1:3000/d/ray-assignment. Username: `admin`.
Read the password from the ignored local file `runtime/grafana-password`.
Do not commit, copy into documentation, or send this file in chat.

The terminal must remain running. Ctrl-C closes access. The Kubernetes service
is ClusterIP, with no Ingress, ALB, NodePort or public listener. Anonymous access
and self-registration are disabled. This is localhost HTTP, not an externally
trusted HTTPS service; no domain or certificate is needed. Do not change the
bind address to 0.0.0.0 to share it. Dashboard provisioning is version-controlled;
Grafana's local database is ephemeral and manual edits/users are lost on restart.
Prometheus retains six hours of metrics. Ray panels show no data until a local
Ray workload is running or has run within the selected time range; this is not
live telemetry from the deleted AWS cluster.

The chart disables Grafana by default, so changing cloud observability does not
silently install it. The local setup explicitly enables it and disables AWS log
shipping. Grafana runs non-root with resource limits, a read-only root filesystem,
no service-account token, and a digest-pinned image.

An ALB receives inbound application requests; it does not restrict a build's
outbound HTTPS access. Neither repository visibility nor localhost Grafana fixes
CodeBuild egress. The separately documented exception covers only TCP 443 on the
CI runner and expires on 2026-11-01 UTC. Production needs enforced destination
filtering or suitable private connectivity, with its cost and dependency access
tested before removing the exception.

## GitHub Free and review pause

At the owner's request the repository stays public, preserving GitHub Free's
required CI/branch-protection support. Private personal repositories require a
paid plan for equivalent protected-branch enforcement. No subscription was bought.

Independent review is temporarily **not enforced**. CODEOWNERS remains documented
and its comments explain the pause; comments alone do not enforce a review policy.
The active settings are `security/branch-protection.json`. Restore peer review:

```sh
gh api --method PUT repos/SumitSharma-DevOps-3107/contexq-assignment/branches/main/protection \
  --input security/branch-protection-with-review.json
```

Add a second reviewer with repository write access to CODEOWNERS before restoring
required code-owner approval for owner-authored PRs. Current policy still requires
passing validate/security/pr-title checks, resolved conversations, an up-to-date
branch, and includes administrators. Force pushes and deletion remain disabled.
Document this pause and the temporary egress exception in the final release; do
not describe them as independently reviewed or production-complete controls.
