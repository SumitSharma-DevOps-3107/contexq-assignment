# Local validation

## Native macOS baseline: passed

- Five pytest tests passed, including real Iceberg insert, no-op rerun, and update.
- `pip check`: no broken requirements.
- Native Ray pipeline executed twice successfully.
- Input: two CSVs of 1,200 records each; canonical output: 1,800 companies.
- First run: 1,800 inserts. Second run: zero inserts and zero updates, retaining
  the same Iceberg snapshot ID.
- Training: 1,440 companies; held-out evaluation: 360 companies.
- Synthetic holdout R²: 0.983635; MAE: approximately USD 20.25 million.
  Targets are synthetic and typically large; these metrics are demonstration
  results and cannot be interpreted as business accuracy.
- Persisted outputs: `runtime/run.json`, `runtime/catalog.db`,
  `runtime/warehouse/`, and `runtime/model/`.

## Kubernetes baseline: passed

Two kind nodes reached Ready and KubeRay 1.5.1 was installed. The Linux ARM64
container was built using the offline-wheel fallback after Docker VM package
downloads failed. The RayJob finished with `SUCCEEDED` / `Complete` in about
28 seconds. Its report identifies the dedicated resolver worker pod as the actor
host. First commit: 1,800 inserts; model R²: 0.983644. Reports and status evidence
are stored in `docs/evidence/`. The head and system operator are assigned to the
system node, and the Ray worker is assigned to the separate worker node.

A fresh-cluster rerun initially failed because the head reached its 1.5 GiB memory
limit. After raising that limit to 2 GiB, the rerun succeeded in about 29 seconds:
zero inserts, zero updates, 1,800 companies, and the same Iceberg snapshot as the
first Kubernetes run. This verifies persistence across Ray cluster lifecycles.
The resolver hostname again matched the dedicated worker pod. The Ray memory
monitor remains enabled. The failed run's diagnostic log is retained locally in
`runtime/memory-failure.log`.

## Remaining assignment validation

Cloud identity, S3/Glue, Terraform, autoscaling, Spot interruptions, CI/CD,
distributed Ray Train, Prometheus and central logging are not yet validated.
