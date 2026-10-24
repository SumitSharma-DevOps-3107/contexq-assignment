"""Digest-only RayJob deployment with a finite wait and cleanup on every outcome."""
import json
import os
import subprocess
import time
from pathlib import Path

import yaml

from ci_common import check_budget, image_uri, load_config, save_result


def main():
    config = load_config()
    check_budget(config)
    request = json.loads(Path("ci-request.json").read_text())
    os.environ["RAY_IMAGE"] = image_uri(config, request["image"])
    os.environ["CI_ENVIRONMENT_FILE"] = "runtime/ci-environment.json"
    os.environ["PATH"] = str(Path(".tools").resolve()) + os.pathsep + os.environ["PATH"]
    os.environ["KUBECONFIG"] = str(Path("runtime/ci-kubeconfig").resolve())
    subprocess.run(["aws", "eks", "update-kubeconfig", "--name", config["cluster"], "--region", config["region"]], check=True)
    command = ["kubectl", "-n", "ray-assignment"]
    existing = json.loads(subprocess.check_output(command + ["get", "rayjobs", "-o", "json"]))
    if any(x.get("status", {}).get("jobDeploymentStatus") not in ("Complete", "Failed") for x in existing["items"]):
        raise SystemExit("Another RayJob is active; refusing overlapping compute")
    subprocess.run(["python3", "scripts/render-aws-job.py"], check=True)
    manifest = yaml.safe_load(Path("runtime/aws-rayjob.yaml").read_text())
    manifest["metadata"]["labels"] = {"app.kubernetes.io/managed-by": "github-actions", "ci-commit": request["commit"]}
    manifest["spec"]["backoffLimit"] = 0
    manifest["spec"]["activeDeadlineSeconds"] = 900
    Path("runtime/aws-rayjob.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    job = json.loads(subprocess.check_output(command + ["create", "-f", "runtime/aws-rayjob.yaml", "-o", "json"]))
    name = job["metadata"]["name"]
    result = {"job": name, "image": request["image"], "commit": request["commit"], "status": "TIMEOUT"}
    try:
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            status = json.loads(subprocess.check_output(command + ["get", "rayjob", name, "-o", "json"])).get("status", {})
            phase = status.get("jobStatus", "PENDING")
            print(f"{name}: {phase}", flush=True)
            if phase in ("SUCCEEDED", "FAILED", "STOPPED") or status.get("jobDeploymentStatus") == "Failed":
                result.update(status=phase, ray_status=status)
                break
            time.sleep(15)
        save_result("deploy", result)
        if result["status"] != "SUCCEEDED":
            raise SystemExit("RayJob did not succeed; inspect saved result and pod logs")
    finally:
        subprocess.run(command + ["delete", "rayjob", name, "--wait=true", "--timeout=60s"], check=True)


if __name__ == "__main__":
    main()
