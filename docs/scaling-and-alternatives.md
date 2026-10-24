# Scaling, Spot resilience and a managed alternative

## Ray Data and Train configuration

The working model is a deterministic CPU sklearn baseline in the driver. It is
not distributed training. Ray Data reads two CSV blocks; driver collection is
explicitly capped at 100,000 records. This keeps the take-home reproducible but
must change before a large production workload.

For large ingestion, partition input into many appropriately sized Parquet files,
use streaming Ray Data transformations and distributed joins instead of collecting
the dataset into pandas. Tune read and map concurrency to actual worker CPUs and
S3 throughput, rather than creating thousands of tiny tasks. Measure object-store
use and spill I/O in Prometheus. Keep transient spilling on adequately sized local
disks; durable outputs and checkpoints belong in S3.

The head advertises zero task CPUs. EntityResolver requires one `entity_resolver`
custom resource supplied only by Ray workers; Kubernetes labels and the worker
pool taint enforce physical placement. Kill the resolver actor after use so its
CPU/custom resource is available for later stages.

The current head has a 256MiB object store, 384MiB `/dev/shm`, and a 2GiB container
limit. Workers have 384MiB object stores, 512MiB `/dev/shm`, and 2GiB limits. Shared
memory is counted inside those limits. Leave room for the Python heap, Ray control
processes and model state; a bigger shared-memory mount is not additional RAM.

A future CPU distributed TorchTrainer can use `ScalingConfig(num_workers=2,
use_gpu=False, resources_per_worker={"CPU": 1}, placement_strategy="SPREAD")` with
two available Ray workers. Pass a Ray Dataset into the trainer and consume each
worker's dataset shard in the training loop. Use the framework's distributed model
preparation, report metrics consistently from all ranks and checkpoint model plus
optimizer/epoch state to the authorized S3 artifacts prefix. All workers need the
same pinned framework build and matching IRSA access. This is a design example,
not an installed Torch dependency or a claim of a completed distributed test.

Ray Train reserves resources for the whole worker group. Ensure those resources
fit simultaneously, including CPU/memory for its coordinator. SPREAD distributes
when possible; use STRICT_SPREAD only when separate Ray nodes are required and
capacity is guaranteed. The demo's maximum two workers is a budget constraint.
GPU training requires a separate GPU-capable pool, device plugin, matching CUDA
image and GPU requests in both Kubernetes and Ray; none are provisioned here.

See [Ray Train scale configuration](https://docs.ray.io/en/latest/train/user-guides/using-accelerators.html).

## Spot resilience

The system/head pool uses On-Demand capacity; workers use diversified ARM Spot
instance types across two AZs. Kubernetes Cluster Autoscaler sizes EC2 capacity;
Ray's autoscaler sizes worker pods. Terraform ignores desired-size changes owned
by the autoscaler. Max desired workers is two, but EC2 replacement/rebalance can
briefly overlap terminating instances, so it is not a hard instantaneous cost cap.

EntityResolver is deterministic and supports two actor restarts/task retries.
The Iceberg upsert uses stable company keys and an atomic catalog commit; already
committed input reruns insert/update zero rows. In-memory intermediate data can
be recomputed. This does not provide general multi-writer isolation or guarantee
progress during prolonged Spot capacity shortage. RayJob retry is bounded; CI
uses zero whole-job retries and surfaces failure to avoid hidden spend.

For real production Spot recovery, consume interruption notices, drain gracefully,
checkpoint training periodically and resume the entire distributed worker group
from its latest durable checkpoint. A CPU model with no mid-training checkpoint
must restart training. Head-node failure is also a separate recovery problem.

Validated so far: worker autoscaling/cold start, scoped identity, persistent
Iceberg/S3 results and idempotent reruns. A deliberate EC2 Spot interruption has
not been tested; do not present pod replacement as proof of a real Spot notice.

## Alternative without managing Kubernetes

A serverless design for this small CPU workload is EventBridge Scheduler → Step
Functions → AWS Glue Spark for ingest/entity-resolution/Iceberg updates → an ECS
Fargate task running the sklearn training container → S3 model/metrics. Glue uses
the existing S3 warehouse and Glue Data Catalog; Fargate removes EC2 management.
Step Functions owns sequencing, retries and timeouts. Scope a separate execution
role for each stage and pin the training image by digest.

This removes EKS control-plane/node/operator administration, but requires replacing
the distributed Ray actor APIs and changing the pipeline into separate stages.
Startup latency and service limits differ. Job/task costs still need limits; this
is not assumed cheaper without measuring the workload. For larger distributed or
GPU training, use an on-demand SageMaker training job instead of Fargate; that is
managed ephemeral training compute, not serverless inference.

This is a design alternative only; no extra services are provisioned for this demo.

See [Glue Iceberg support](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html),
[Step Functions ECS/Fargate integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-ecs.html)
and [SageMaker training integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-sagemaker.html).
