import json
import os
import uuid
from pathlib import Path

import ray

from ray_platform.core import commit, harmonize, resolve, train
from ray_platform.cloud import CloudSettings


@ray.remote(num_cpus=1, resources={"entity_resolver": 1}, max_restarts=2, max_task_retries=2)
class EntityResolver:
    def resolve_batch(self, frame):
        placement = dict(node_id=ray.get_runtime_context().get_node_id(), hostname=os.uname().nodename)
        if os.getenv("CATALOG_TYPE") == "glue":
            import boto3
            placement["aws_identity_arn"] = boto3.client("sts").get_caller_identity()["Arn"]
        return resolve(frame), placement


def main():
    cloud = CloudSettings.from_env()
    if os.getenv("RAY_ADDRESS"):
        ray.init(address=os.environ["RAY_ADDRESS"])
    else:
        ray.init(num_cpus=2, resources={"entity_resolver": 1},
                 object_store_memory=256 * 1024 * 1024, include_dashboard=False)
    try:
        data = Path(os.getenv("DATA_DIR", "data")).resolve()
        root = Path(os.getenv("OUTPUT_DIR", "runtime")).resolve()
        inputs = cloud.inputs if cloud else [str(data / "supply.csv"), str(data / "financial.csv")]
        dataset = ray.data.read_csv(inputs,
                                    override_num_blocks=2)
        # Bound this take-home driver materialization to a documented small-data limit.
        combined = dataset.to_pandas(limit=100_000)
        actor = EntityResolver.remote()
        resolved, placement = ray.get(actor.resolve_batch.remote(combined))
        ray.kill(actor)
        canonical = harmonize(resolved)
        committed, transaction = commit(canonical, root, cloud)
        metrics = train(committed, root / "model")
        report = dict(input_rows=len(combined), canonical_rows=len(committed),
                      resolver=placement, iceberg=transaction, model=metrics)
        run_id = os.getenv("RUN_ID", uuid.uuid4().hex)
        if cloud:
            import boto3
            report["driver_aws_identity_arn"] = boto3.client("sts").get_caller_identity()["Arn"]
            report["artifacts"] = f"s3://{cloud.bucket}/artifacts/{run_id}/"
        (root / "run.json").write_text(json.dumps(report, indent=2))
        if cloud:
            cloud.publish(root, run_id)
        print(json.dumps(report, indent=2), flush=True)
    finally:
        ray.shutdown()


if __name__ == "__main__":
    main()
