# Private EKS evidence walkthrough

Use this runbook only during an approved compute window. The demo has no public
ALB, DNS name or public TLS certificate. Browser HTTP endpoints bind to loopback;
SSM carries traffic to the private API, whose hostname and CA remain verified.
The application image used in the recorded evidence is a functional immutable
release, not an approved golden image. Cloud CI stays disabled between windows.

## Before starting

Refresh AWS browser login, source `scripts/aws-env.sh`, and verify the expected
account with `aws sts get-caller-identity`. Check gross cost before credits,
including an allowance for unposted usage. Set an explicit UTC lease of two
hours in the ignored compute variables. The configuration generator preserves an
existing deadline, but regenerates other fields: set `enable_demo_ssm = true`
in the ignored compute variables after running it. This grants the system node
the SSM session permissions used for the demonstration.

Initialize and apply reviewed, scanned plans in the order described in
`infra/README.md`. Do not reuse a saved plan after apply, state changes or lease
expiry. A cloud-side guard deletes the named compute and NAT resources after the
lease, independently of this laptop; it is not a hard billing cap.

## Reach the private API

After both node groups are ready, obtain the endpoint hostname and the one
running system instance from AWS. Confirm the instance is Online in Systems
Manager. In a dedicated terminal, forward the private endpoint through it:

```sh
aws ssm start-session --target "$SYSTEM_INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$EKS_HOST\"],\"portNumber\":[\"443\"],\"localPortNumber\":[\"18443\"]}"
```

In another terminal run the narrowly scoped CONNECT bridge:

```sh
.venv/bin/python scripts/eks-tunnel-proxy.py --host "$EKS_HOST"
```

Create an isolated kubeconfig and configure the proxy:

```sh
export KUBECONFIG="$PWD/runtime/eks-evidence-kubeconfig"
aws eks update-kubeconfig --name ray-assignment --alias ray-assignment-evidence --kubeconfig "$KUBECONFIG"
CLUSTER_ARN=$(aws eks describe-cluster --name ray-assignment --query cluster.arn --output text)
kubectl config set-cluster "$CLUSTER_ARN" --proxy-url=http://127.0.0.1:18444
```

Keep the original server hostname and certificate authority supplied by
`aws eks update-kubeconfig`.
Do not use insecure TLS flags. Export `KUBECONFIG` to that isolated file and
verify `kubectl get nodes`. For Terraform platform commands, export
`TF_VAR_private_api_proxy_url=http://127.0.0.1:18444`.

Apply platform first with Grafana disabled. Create the `ray-grafana-admin`
Secret in `ray-assignment` from a private local password file, key `password`.
Use `--from-file=password=<private-file>` and pipe dry-run YAML directly into
`kubectl apply`; never put the value in Terraform, Git, a screenshot or a log.
Then plan and apply platform with `TF_VAR_enable_grafana=true`. Review that this
second plan changes only the observability release.

## Execute and capture

Render a RayJob with `scripts/render-aws-job.py` using an immutable ECR digest.
For a temporary screenshot copy only, set `shutdownAfterJobFinishes: false`,
remove `ttlSecondsAfterFinished`, keep an execution deadline, and retain one
worker with `minReplicas: 1`. This keeps the completed job and metrics available
for capture. Normal jobs retain automatic cleanup and worker scale-to-zero.
Submit this copy through the isolated kubeconfig and verify `SUCCEEDED`.

Run each forwarding command in its own terminal:

```sh
kubectl -n ray-assignment port-forward service/ray-grafana 13000:3000 --address 127.0.0.1
kubectl -n ray-assignment port-forward service/ray-prometheus 19090:9090 --address 127.0.0.1
kubectl -n ray-assignment port-forward "pod/$RAY_HEAD_POD" 18265:8265 --address 127.0.0.1
```

Capture these views in Chrome while the lease remains valid:

1. Grafana at `http://127.0.0.1:13000`: sign in, open Ray Assignment Workload
   Metrics, and verify two Ray targets, one cluster, task counts and CPU data.
2. Ray at `http://127.0.0.1:18265`: authenticate with the current head's
   `ray get-auth-token` value, then show the new job's successful execution.
3. The same Ray job's driver logs. Preserve full logs privately; a screenshot
   can clip long lines. This is not a CloudWatch screenshot.
4. Prometheus at `http://127.0.0.1:19090/alerts`: show both alert rules and
   explain normal inactive state. Run the repository promtool fixtures inside
   the EKS Prometheus deployment and save their output to demonstrate firing
   and recovery. No external paging receiver is configured.

Run the fixtures against the explicitly selected EKS kubeconfig:

```sh
tar -cf - tests/alerts.test.yml charts/observability/files/alerts.yml |
  kubectl -n ray-assignment exec -i deployment/ray-prometheus -- sh -c '
    set -eu
    d=$(mktemp -d /prometheus/.alert-tests.XXXXXX)
    trap "rm -rf \"$d\"" EXIT
    export TMPDIR="$d"
    cd "$d"
    tar -xf -
    promtool test rules tests/alerts.test.yml
  '
```

Verify fresh CloudWatch events in `/ray-assignment/pods` for both `ray-head`
and `ray-worker`, scoped to this job's creation time. Save a sanitized summary.
Check driver and worker IRSA, expected input/output counts, and idempotent
Iceberg results. Distinguish actual cloud evidence from the separate local
rehearsal. Never capture tokens or password-entry screens.

## End the window

Save evidence before teardown. A full platform destroy also deletes the
CloudWatch log group and logging IAM role; review that scope separately. The
recorded capture run retained logs and IAM and removed only the named EKS
compute, NAT and EIP through AWS APIs. In-cluster Prometheus storage is ephemeral.
For full Terraform cleanup, account for CI dependencies in `docs/cicd.md`.
Retain encrypted data, state and their keys. If the lease already
removed the cluster, reconcile only resources proven absent; never discard
live AWS resources from state merely to make a plan pass.

Verify the cluster and node groups are absent and there are no assignment EC2
instances, active NAT gateways or allocated NAT EIPs. Stop the local forwarding
processes and remove the temporary credential. Record the cleanup timestamp and
posted gross cost, explicitly noting billing delay and retained-resource costs.
