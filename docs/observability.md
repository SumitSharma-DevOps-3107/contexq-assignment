# Observability and troubleshooting

`infra/platform/observability.tf` installs the local `charts/observability` Helm
chart and creates a three-day CloudWatch log group plus a dedicated IRSA role.
The logging role can create streams and write events only in `/ray-assignment/pods`.
It cannot read data, Terraform state, Secrets, or change log retention.

Prometheus runs one replica on the existing system pool, with 100m CPU/128MiB
requested and 500m CPU/512MiB limits. A 512MiB emptyDir holds its database, bounded
by six hours and 256MB of block retention (WAL/head overhead also consumes space).
Metrics are intentionally ephemeral on pod/node replacement. This demo is not HA;
production should use persistent storage or a managed metrics backend.

Ray head and worker containers expose a named metrics port at 8080. Namespaced pod
discovery selects only Ray pods and labels samples by cluster, pod, node and Ray
node type. Scrapes run every ten seconds. No node-exporter is installed: node
metrics are Ray's view of the node/container, not a complete Kubernetes inventory.

Fluent Bit runs on both pools with the worker taint tolerated. It tails CRI
stdout/stderr for Ray head, worker and submitter containers in `ray-assignment`
only. Stream names include the source filename/pod/container for correlation.
It runs as root solely to read host log files, drops all capabilities, has a
read-only root filesystem and mounts `/var/log` read-only. Buffers are bounded
and ephemeral; retries are finite. Node loss or prolonged CloudWatch failure can
lose buffered events. It has no Kubernetes API read permissions. The dedicated
service-account token supplies IRSA, with EC2 metadata fallback disabled.

## View metrics and alerts

```sh
source scripts/aws-env.sh
export KUBECONFIG="$PWD/runtime/eks-kubeconfig"
kubectl -n ray-assignment port-forward --address 127.0.0.1 service/ray-prometheus 9090:9090
```

Open http://127.0.0.1:9090. `/targets` shows live head and worker endpoints;
`/alerts` evaluates endpoint failures and sustained container memory pressure.
There is no Alertmanager or external notification integration in this demo.
An idle/deleted Ray cluster has no targets; that is expected, not a failure.

Useful PromQL queries:

```promql
up{job="ray"}
sum by (ray_cluster, State) (ray_tasks{job="ray"})
ray_node_cpu_utilization{job="ray"}
sum by (ray_cluster, Location) (ray_object_store_memory{job="ray"})
ray_node_cgroup_mem_used{job="ray"} / ray_node_cgroup_mem_total{job="ray"}
sum by (ray_cluster) (ray_cluster_active_nodes{job="ray"})
```

Task metrics must be summed across reporting components. Alert on sustained
conditions: Ray state metrics are eventually consistent. Prometheus and Ray
Dashboard services stay ClusterIP; never bind port-forward to `0.0.0.0`.

## Ray Dashboard

While a RayJob is active, run `bash scripts/dashboard.sh`. It binds to localhost
and uses your authenticated Kubernetes access. Open http://127.0.0.1:8265 and
enter the per-cluster token in Ray's login dialog. Retrieve it in your own terminal:

```sh
source scripts/aws-env.sh
export KUBECONFIG="$PWD/runtime/eks-kubeconfig"
head=$(kubectl -n ray-assignment get pods -l ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
kubectl -n ray-assignment exec "$head" -c ray-head -- ray get-auth-token
```

Do not copy tokens into Git, screenshots, CI logs or chat. Dashboard access can
submit code and is privileged. No public ingress or load balancer is installed.
A completed job is removed after its TTL, so inspect it during execution.

## Central logs

Use CloudWatch Logs in the configured region and open `/ray-assignment/pods`.
An owner can also run `aws logs tail /ray-assignment/pods --since 15m`. Logs may
contain account/resource metadata; keep raw exports private. Example Logs Insights:

```text
fields @timestamp, @logStream, @message
| filter @message like /ERROR|Traceback|OutOfMemory|SUCCEEDED/
| sort @timestamp desc
| limit 100
```

For missing metrics inspect Prometheus targets, pod readiness and named ports.
For missing logs inspect collector logs, IRSA trust, CloudWatch write permissions
and outbound HTTPS. For memory pressure reduce ingestion concurrency/batch size;
shared memory counts toward the container limit. Inspect spilling before raising
limits. Run `promtool check config /etc/prometheus/prometheus.yml` inside the
Prometheus pod after configuration changes.

`verify-observability.py` is an owner-run bounded smoke test using private CI
settings, the existing image digest, and the same budget/lease checks. It verifies
real Ray metrics, centralized head/worker logs and unauthenticated dashboard
rejection, then deletes its RayJob in a finally block. Evidence contains only
sanitized booleans and metric/container names. It requires AWS CLI, kubectl,
PyYAML, an exported KUBECONFIG, RAY_IMAGE and CI_ENVIRONMENT_FILE; see the AWS setup.

Local metrics-only use:

```sh
helm upgrade --install ray-observability charts/observability \
  --namespace ray-assignment --kube-context kind-ray-assignment
```

Logging is off by default; the local cluster does not inherit an AWS role.

References: [Ray metrics](https://docs.ray.io/en/latest/ray-observability/reference/system-metrics.html),
[KubeRay metrics](https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/prometheus-grafana.html),
[Ray authentication](https://docs.ray.io/en/latest/ray-core/internals/token-authentication.html),
[Fluent Bit CloudWatch output](https://docs.fluentbit.io/manual/data-pipeline/outputs/cloudwatch).

## Assignment presentation

Use `docs/observability-demo.md` for the recommended stack, a repeatable walkthrough,
and the explicit production limitations. Run `bash scripts/test-monitoring-alerts.sh`
against local kind to verify pending/firing/resolved alert behavior using synthetic
inputs. This is rule validation, not proof of delivered external notifications.
The earlier AWS commands in this document require an active, authorized cloud
window and private API connectivity; the previous EKS lease has expired.
