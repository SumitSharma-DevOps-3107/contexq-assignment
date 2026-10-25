"""Read-only plans for all layers, run within the existing VPC."""
import json
import os
import subprocess
import tempfile
import importlib.util
from pathlib import Path

from ci_common import check_budget, load_config, save_result


def main():
    config = load_config()
    check_budget(config)
    os.environ["PATH"] = str(Path(".tools").resolve()) + os.pathsep + os.environ["PATH"]
    cache = Path("runtime/provider-cache").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["TF_PLUGIN_CACHE_DIR"] = str(cache)
    spec = importlib.util.spec_from_file_location("security_scan", Path(__file__).with_name("security-scan.py"))
    security_scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(security_scan)
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
        # Saved plans contain secrets: ephemeral private directory, never public artifacts.
        with tempfile.TemporaryDirectory(prefix="ray-plan-") as temporary:
            binary = Path(temporary) / "plan.tfplan"
            plan_json = Path(temporary) / "plan.json"
            plan = subprocess.run(["terraform", f"-chdir={folder}", "plan", "-input=false", "-lock=false", "-no-color", "-detailed-exitcode", f"-out={binary}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            results[layer] = {"exit_code": plan.returncode, "changes": plan.returncode == 2, "security_passed": False}
            output.append(f"\n===== {layer} =====\n{plan.stdout}")
            if plan.returncode in (0, 2):
                try:
                    with plan_json.open("w") as stream:
                        subprocess.run(["terraform", f"-chdir={folder}", "show", "-json", str(binary)], stdout=stream, stderr=subprocess.DEVNULL, check=True)
                    findings = security_scan.scan(plan_json)
                    results[layer].update(security_passed=not findings, findings=findings)
                except Exception:
                    # No exception text: provider/parse errors can contain resolved secrets.
                    results[layer]["security_error"] = "Plan security scan failed; inspect private runner"
    save_result("plan", {"layers": results}, "\n".join(output))
    print(json.dumps(results))
    if any(r["exit_code"] not in (0, 2) or not r["security_passed"] for r in results.values()):
        raise SystemExit("One or more Terraform plans or security gates failed; see sanitized summary")


if __name__ == "__main__":
    main()
