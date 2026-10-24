"""Read-only plans for all layers, run within the existing VPC."""
import json
import os
import subprocess
from pathlib import Path

from ci_common import check_budget, load_config, save_result


def main():
    config = load_config()
    check_budget(config)
    os.environ["PATH"] = str(Path(".tools").resolve()) + os.pathsep + os.environ["PATH"]
    cache = Path("runtime/provider-cache").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["TF_PLUGIN_CACHE_DIR"] = str(cache)
    results, output = {}, []
    for layer in ("bootstrap", "data", "compute", "ci", "platform"):
        folder = Path("infra", layer)
        (folder / "terraform.tfvars.json").write_text(json.dumps(config["tfvars"][layer]))
        args = ["terraform", f"-chdir={folder}", "init", "-input=false", "-lockfile=readonly"]
        if layer != "bootstrap":
            args += [f"-backend-config=bucket={config['state_bucket']}", f"-backend-config=key={layer}/terraform.tfstate", f"-backend-config=region={config['region']}", "-backend-config=encrypt=true", "-backend-config=use_lockfile=true"]
        else:
            subprocess.run(["aws", "s3", "cp", f"s3://{config['state_bucket']}/bootstrap/bootstrap-backup.tfstate", str(folder / "terraform.tfstate"), "--only-show-errors"], check=True)
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
        # No lock writes, no saved binary plans, and never an apply command.
        plan = subprocess.run(["terraform", f"-chdir={folder}", "plan", "-input=false", "-lock=false", "-no-color", "-detailed-exitcode"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        results[layer] = {"exit_code": plan.returncode, "changes": plan.returncode == 2}
        output.append(f"\n===== {layer} =====\n{plan.stdout}")
    save_result("plan", {"layers": results}, "\n".join(output))
    print(json.dumps(results))
    if any(r["exit_code"] not in (0, 2) for r in results.values()):
        raise SystemExit("One or more Terraform plans failed; see plan artifact")


if __name__ == "__main__":
    main()
