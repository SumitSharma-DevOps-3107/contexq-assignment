"""Publish non-credential CI settings after the owner applies infra/ci locally."""
import json
import subprocess
from pathlib import Path


def output(layer):
    values = json.loads(subprocess.check_output(["terraform", f"-chdir=infra/{layer}", "output", "-json"]))
    return {key: value["value"] for key, value in values.items()}


def main():
    settings = {layer: json.loads(Path(f"infra/{layer}/terraform.tfvars.json").read_text())
                for layer in ("bootstrap", "data", "compute", "ci", "platform")}
    ci, data, compute, bootstrap = output("ci"), output("data"), output("compute"), output("bootstrap")
    account = settings["compute"]["expected_account_id"]
    identity = json.loads(subprocess.check_output(["aws", "sts", "get-caller-identity"]))
    if identity["Account"] != account:
        raise SystemExit("Unexpected AWS account")
    config = {"account": account, "region": settings["compute"]["region"],
              "state_key_arn": bootstrap["state_key_arn"],
              "state_bucket": settings["compute"]["state_bucket"], "lease_expires_at": compute["lease_expires_at"],
              "cluster": compute["cluster_name"], "tfvars": settings,
              **{key: data[key] for key in ("bucket", "database", "repository_url")}}
    Path("runtime").mkdir(exist_ok=True)
    path = Path("runtime/ci-environment.json")
    path.write_text(json.dumps(config, indent=2))
    subprocess.run(["aws", "s3", "cp", str(path), f"s3://{ci['ci_bucket']}/config/environment.json", "--only-show-errors"], check=True)
    variables = {"AWS_ACCOUNT_ID": account, "AWS_REGION": config["region"], "AWS_CI_BUCKET": ci["ci_bucket"],
                 "AWS_PLAN_ROLE_ARN": ci["github_plan_role"], "AWS_DEPLOY_ROLE_ARN": ci["github_deploy_role"],
                 "AWS_PLAN_PROJECT": ci["plan_project"], "AWS_DEPLOY_PROJECT": ci["deploy_project"],
                 "ECR_REPOSITORY_URI": data["repository_url"]}
    for name, value in variables.items():
        subprocess.run(["gh", "variable", "set", name, "--repo", settings["ci"]["github_repository"], "--body", value], check=True)
    print("Published CI settings and repository variables; CICD_ENABLED is unchanged.")


if __name__ == "__main__":
    main()
