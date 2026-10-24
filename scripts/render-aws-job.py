"""Render the tested local RayJob into an AWS profile; output remains ignored."""
import copy
import json
import os
import subprocess
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if os.getenv("CI_ENVIRONMENT_FILE"):
    config = json.loads(Path(os.environ["CI_ENVIRONMENT_FILE"]).read_text())
    outputs = {key: {"value": config[key]} for key in ("repository_url", "bucket", "database")}
else:
    outputs = json.loads(subprocess.check_output(["terraform", "-chdir=infra/data", "output", "-json"], text=True))
image = os.environ.get("RAY_IMAGE", "")
repo = outputs["repository_url"]["value"]
if not (image.startswith(repo + ":") or image.startswith(repo + "@sha256:")) or image.endswith(":latest"):
    raise SystemExit("Set RAY_IMAGE to a versioned image or digest in this stack's ECR repository")
region = os.environ["AWS_REGION"]
job = yaml.safe_load(Path("k8s/rayjob.yaml").read_text())
job["metadata"]["generateName"] = "corporate-aws-"
job["spec"]["backoffLimit"] = 1
job["spec"]["submitterPodTemplate"] = {"spec": {
    "restartPolicy": "Never",
    "nodeSelector": {"assignment-pool": "system"},
    "containers": [{
        "name": "ray-job-submitter", "image": image,
        "resources": {"requests": {"cpu": "100m", "memory": "200Mi"},
                      "limits": {"cpu": "500m", "memory": "512Mi"}},
        "securityContext": {"runAsNonRoot": True, "runAsUser": 1000,
                            "allowPrivilegeEscalation": False,
                            "capabilities": {"drop": ["ALL"]}},
    }],
}}
cluster = job["spec"]["rayClusterSpec"]
cluster["enableInTreeAutoscaling"] = True
head = cluster["headGroupSpec"]["template"]["spec"]
worker_group = cluster["workerGroupSpecs"][0]
worker_group.update(minReplicas=0, maxReplicas=2)
worker = worker_group["template"]["spec"]
worker["tolerations"] = [{"key": "workload", "operator": "Equal", "value": "ray", "effect": "NoSchedule"}]
head.pop("tolerations", None)
head["volumes"][0] = {"name": "output", "emptyDir": {"sizeLimit": "1Gi"}}
env = [{"name": k, "value": v} for k,v in {
    "CATALOG_TYPE": "glue", "S3_BUCKET": outputs["bucket"]["value"],
    "GLUE_DATABASE": outputs["database"]["value"], "AWS_REGION": region,
    "AWS_DEFAULT_REGION": region, "AWS_EC2_METADATA_DISABLED": "true",
    "RAY_USAGE_STATS_ENABLED": "0",
}.items()]
for pod in (head, worker):
    pod["serviceAccountName"] = "ray-pipeline"
    pod["securityContext"] = {"fsGroup": 1000, "seccompProfile": {"type": "RuntimeDefault"}}
    for container in pod["containers"]:
        container["image"] = image
        container["imagePullPolicy"] = "IfNotPresent"
        container["env"] = copy.deepcopy(env)
Path("runtime").mkdir(exist_ok=True)
Path("runtime/aws-rayjob.yaml").write_text(yaml.safe_dump(job, sort_keys=False))
print("Rendered runtime/aws-rayjob.yaml")
