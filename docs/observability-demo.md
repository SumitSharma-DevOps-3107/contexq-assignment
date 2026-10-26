# Observability recommendation and reviewer walkthrough

## Recommended solution for this assignment

Use **Prometheus + Grafana + the Ray Dashboard**, with **Fluent Bit → CloudWatch
Logs on AWS**. This matches Ray's Prometheus metrics and the existing tested
implementation. Run the demonstration on the existing local kind cluster; use
sanitized evidence for the AWS integrations already tested. Do not recreate EKS
merely to keep dashboards populated. The $30 budget is a total spending ceiling,
not an always-on hosting allowance.

| Capability | Assignment implementation | Demonstration / evidence |
|---|---|---|
| Metrics and trends | Prometheus scrapes Ray head/worker metrics every 10 seconds; Grafana shows tasks, CPU, active clusters and scrape health | Live local dashboard and a bounded RayJob |
| Workload diagnosis | Token-protected Ray Dashboard; Kubernetes job status and container logs | Inspect a running local job, then successful completion |
| Centralized AWS logs | Fluent Bit with scoped IRSA, three-day CloudWatch retention | Previously verified head/worker delivery; `evidence/observability-validation.json` |
| Alert detection | Endpoint unavailable for 1 minute; memory above 85% for 2 minutes | `bash scripts/test-monitoring-alerts.sh` proves pending, firing and recovery |
| Resilience | Real FIS Spot interruption, actor recovery and idempotent data rerun | `evidence/spot-recovery.json`; no need to pay for another interruption |
| Access control | Localhost port-forward, Grafana login, Ray token authentication | Anonymous Grafana API rejected with 401; no public ingress |

Ray recommends Prometheus/Grafana for historical metrics alongside its diagnostic
Dashboard: [Ray observability](https://docs.ray.io/en/latest/ray-observability/getting-started.html).
Alertmanager would add grouping, routing, silences and delivery to a receiver;
Prometheus rule evaluation alone does not deliver a notification:
[Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/).

## Repeatable 8–10 minute walkthrough

1. **Architecture and scope (1 minute).** Explain metrics, logs and diagnostic UI
   separately. Say: “This is live local telemetry; the AWS evidence comes from our
   completed bounded cloud test.” Show the implementation/evidence table above.
2. **Authenticated dashboard (1 minute).** If access is not already running, start
   `bash scripts/grafana-local.sh`. Open http://127.0.0.1:3000/d/ray-assignment.
   Sign in as `admin` using the private `runtime/grafana-password` file. Do not
   screen-share the password or token. Select the last 15 minutes and 10s refresh.
3. **Run a real workload (2 minutes).** On the prepared Mac, the patched candidate
   has already built and passed two local RayJobs. For a fresh environment, build
   it with `docker build --platform linux/arm64 -t ray-assignment:security-candidate .`.
   Tag/load the local candidate, then submit with the existing single-writer guard:

   ```sh
   docker tag ray-assignment:security-candidate ray-assignment:local
   kind load docker-image ray-assignment:local --name ray-assignment
   bash scripts/submit.sh
   .tools/kubectl --context kind-ray-assignment -n ray-assignment get rayjobs,pods -w
   ```

   Show Ray targets appearing, task activity and CPU changes. Do not invent
   activity when the job has finished: choose the time range containing the run.
   The local candidate remains a demo image, not a vulnerability-approved golden
   release. The watch command is read-only; stop it with Ctrl-C.
4. **Correlate logs and results (1 minute).** Use the job name printed by submit:
   `.tools/kubectl --context kind-ray-assignment -n ray-assignment logs -f job/JOB_NAME`.
   Show completion and `runtime/kubernetes/run.json` if that output is present.
   Show the recorded AWS CloudWatch validation separately. Do not present local
   kubectl logs as persistent centralized logging. Capture logs privately before
   the job TTL deletes its pods if a recording needs them later.
5. **Alert behavior (1 minute).** Run `bash scripts/test-monitoring-alerts.sh` and
   show SUCCESS. Explain the input fixture tests both firing and resolution,
   threshold equality, and no-target idle behavior. This test does not induce a
   real OOM, break a running target, or send email/Slack. Open the alert definitions
   to show severity and the troubleshooting action for each alert.
6. **Cloud resilience and limits (2 minutes).** Show the sanitized Spot and cloud
   observability evidence. Explain the constraints below and the production
   upgrade path. Finish with the successful RayJob and Grafana history, not a
   claim that a live AWS cluster still exists.

For Ray's diagnostic UI during a local job, select the current head pod from
`.tools/kubectl --context kind-ray-assignment -n ray-assignment get pods -l ray.io/node-type=head`.
Use that exact pod name in a localhost-only `port-forward pod/HEAD_POD 8265:8265`
with the same explicit context/namespace and `--address 127.0.0.1`. Retrieve its
Ray token privately using `exec HEAD_POD -c ray-head -- ray get-auth-token` with
that context/namespace. Never put the token in a screenshot or public URL.
The existing `scripts/dashboard.sh` targets AWS; do not use it for this local demo.

## Limitations to disclose in the final release

| Constraint | What it means | Production approach |
|---|---|---|
| $30 total AWS budget | Cloud compute was leased and removed; no always-on EKS, ALB or managed monitoring workspace | Establish a monthly operational budget, cost allocation and monitored cleanup |
| No domain/certificate | Localhost HTTP only; no external trusted HTTPS endpoint is demonstrated | Private connectivity or authenticated ingress with DNS, managed TLS and SSO; network allowlists alone are not user authentication |
| Public repo / GitHub Free | Source is public; credentials and raw cloud evidence remain private. Private-repo equivalent merge enforcement needs an appropriate plan | Use an organization/private repo with supported protection and secret management |
| Review temporarily paused | Required CI is enforced, but independent approval is not | Add a second owner and restore the saved review policy |
| Metrics are ephemeral | One Prometheus replica, six-hour retention, bounded storage; pod/node loss erases history | Persistent storage or remote-write to a managed Prometheus backend, explicit retention/cardinality limits |
| Grafana is ephemeral | Provisioned dashboards survive via Git; manual database edits/users do not | Persistent database, SSO, backup and recovery testing |
| Notifications absent | Two rules evaluate, but no Alertmanager/receiver delivery has been tested | Add Alertmanager and verify firing/resolved delivery to an approved receiver; a local webhook inbox can demonstrate delivery without external messaging credentials |
| Limited Kubernetes coverage | Ray metrics are not a full node/pod inventory; vanished targets and failed jobs are not covered by the two rules | Add kube-state-metrics, job-failure/missing-job detection and node/cAdvisor telemetry with controlled RBAC |
| Logs are bounded | AWS retention is three days; local logs and Fluent Bit buffers can be lost | Define retention and sensitive-data filtering, persistent buffering and ingestion-failure alerts |
| No distributed tracing | Stage-level timing, logs and Ray metrics cover this batch demo; OpenTelemetry traces were not implemented | Add correlated run IDs, structured stage logs and selected OTel spans when debugging complexity justifies it |
| Security work remains | Candidate image has high vulnerabilities; CI HTTPS egress exception expires November 1; KMS/private-API changes passed the October 25 EKS run; CI artifact migration remains unvalidated | Remediate and rescan image, implement controlled egress, validate the documented migration |

Avoid adding Loki, Tempo, Elasticsearch or a managed Grafana workspace solely to
increase the tool count. They introduce storage, access, operational or billing
work without fixing the main demo gap: showing one workload from metrics through
logs, detection, recovery and a documented limitation. Managed services are a
reasonable production option, not required for this assignment; Amazon Managed
Grafana has active-user licensing: [AWS pricing](https://aws.amazon.com/grafana/pricing/).

## Acceptance and fallback

Verified before this walkthrough was written: authenticated local dashboard and
Prometheus datasource; four healthy Ray scrape targets; two successful patched
local jobs; prior AWS head/worker metrics and centralized logs; real Spot recovery.
The added alert rule suite passes all three scenarios, including firing/resolution.
A clean demo should reproduce the local job and metrics, and run the alert suite.

Save screenshots/recordings with timestamps and no secrets. If the laptop or
network fails during the interview, present the version-controlled dashboard,
alert tests and sanitized evidence with their dates. Clearly label them recorded
proof, not a live environment. Do not fabricate metric activity or report AWS
checks as current after the lease has removed the resources.
