"""Small CLI helpers shared by Actions and private CodeBuild jobs; no static keys."""
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"], text=True))


def load_config():
    bucket = os.environ["CI_BUCKET"]
    Path("runtime").mkdir(exist_ok=True)
    subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/config/environment.json", "runtime/ci-environment.json", "--only-show-errors"], check=True)
    config = json.loads(Path("runtime/ci-environment.json").read_text())
    if config["account"] != os.environ["EXPECTED_AWS_ACCOUNT_ID"]:
        raise ValueError("Configuration account mismatch")
    if aws("sts", "get-caller-identity")["Account"] != config["account"]:
        raise ValueError("AWS identity account mismatch")
    return config


def check_budget(config, now=None):
    now = now or datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(config["lease_expires_at"].replace("Z", "+00:00"))
    if (deadline - now).total_seconds() < 1800:
        raise ValueError("Compute lease has less than 30 minutes remaining; CI never renews it")
    budget = aws("budgets", "describe-budget", "--account-id", config["account"], "--budget-name", "ray-assignment-gross-spend", "--region", "us-east-1")["Budget"]
    if budget["BudgetLimit"]["Unit"] != "USD" or float(budget["BudgetLimit"]["Amount"]) > 30:
        raise ValueError("Expected a USD budget of at most 30")
    if budget["CostTypes"].get("IncludeCredit", True) or budget["CostTypes"].get("IncludeRefund", True):
        raise ValueError("Budget must exclude credits and refunds")
    actual = budget.get("CalculatedSpend", {}).get("ActualSpend")
    if actual is None or actual["Unit"] != "USD":
        raise ValueError("Budget spending data unavailable")
    if float(actual["Amount"]) >= 20:
        raise ValueError("CI stopped at USD 20 posted gross spend, preserving USD 10 headroom")
    return float(actual["Amount"])


def image_uri(config, image):
    if not re.fullmatch(re.escape(config["repository_url"]) + r"@sha256:[0-9a-f]{64}", image):
        raise ValueError("Deployment requires a digest in this assignment's ECR repository")
    return image


def save_result(mode, result, text=None):
    build_id = os.environ["CODEBUILD_BUILD_ID"].split(":", 1)[1]
    folder = Path("runtime")
    folder.mkdir(exist_ok=True)
    target = folder / "result.json"
    target.write_text(json.dumps(result, indent=2))
    prefix = f"s3://{os.environ['CI_BUCKET']}/results/{mode}/{build_id}"
    subprocess.run(["aws", "s3", "cp", str(target), prefix + "/result.json", "--only-show-errors"], check=True)
    if text is not None:
        plan = folder / "plan.txt"
        plan.write_text(text)
        subprocess.run(["aws", "s3", "cp", str(plan), prefix + "/plan.txt", "--only-show-errors"], check=True)
