# EKS demonstration evidence

The four JPEG files are real browser captures of the private EKS environment in
Singapore on 26 October 2026. They are separate from the local kind captures in
`../rehearsal`. The successful RayJob is `eks-screenshots-fz4wk`, Ray submission
`eks-screenshots-fz4wk-wbpbn`, completed at 07:48:26 UTC in 15.072 seconds.

| Capture | What it demonstrates |
|---|---|
| 01-grafana-metrics.jpg | Two Ray scrape targets, one cluster, task and CPU telemetry |
| 02-rayjob-succeeded.jpg | Successful cloud job, immutable functional release, execution timestamps |
| 03-rayjob-logs.jpg | Actual driver log lines for the same submission; long lines can clip |
| 04-prometheus-alerts.jpg | Two configured rules, thresholds, actionable descriptions and normal inactive state |

`final-capture-run.json` records sanitized cloud API results. Fresh CloudWatch
streams include both head and worker containers; the driver-log screenshot is
not a CloudWatch UI capture. `final-alert-test-output.txt` records successful
promtool pending/firing/recovery fixtures executed in EKS Prometheus. No external
paging receiver was installed. Dashboard requests without credentials returned
401. Both driver and actor used scoped IRSA.

The pipeline read 2400 rows, produced 1800 companies, and performed zero inserts
or updates on the existing Iceberg table. The retained screenshot cluster showed
idle worker turnover and scrape gaps after completion; autoscaler interaction
needs investigation before a long-lived production deployment. The normal job
configuration cleans up its Ray cluster and scales idle workers to zero.

The ECR image is a previously tested functional release, not a golden-approved
image. The new golden-image security gate remains unsatisfied. Cloud CI is paused.
No public ALB, domain or public certificate was needed: operator access used SSM,
TLS-verified private API access and loopback-only dashboard forwards.

`validation.json` preserves the first 25 October run; `screenshot-run.json`
preserves the second run, which completed without UI captures because browser
access was blocked. The 26 October run replaced that missing screenshot evidence.
Raw logs, credentials, kubeconfigs, state and resolved plans remain ignored.

Cleanup preserves CloudWatch logs, IAM roles, encrypted data and state. Those
retained resources can incur residual costs. Compute cleanup outside Terraform
requires refresh and careful state reconciliation before another deployment.

Cleanup verified at 13:34 UTC on 26 October: cluster absent, no assignment EC2
instances, no active NAT gateways and no allocated EIPs in Singapore. Posted
gross cost: USD 4.18, before credits; billing is delayed and this is not
the final bill.
