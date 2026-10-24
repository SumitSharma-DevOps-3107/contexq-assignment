"""Generate ignored Terraform settings from verified AWS identity, never credentials."""
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
region = os.environ.get("AWS_REGION")
expected = os.environ.get("EXPECTED_AWS_ACCOUNT_ID")
if not region or not expected or not os.getenv("AWS_PROFILE"):
    raise SystemExit("First source scripts/aws-env.sh")


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"], text=True))


identity = aws("sts", "get-caller-identity")
if identity["Account"] != expected:
    raise SystemExit("Refusing to configure a different AWS account")
role = aws("iam", "get-role", "--role-name", os.environ["AWS_PROVISIONING_ROLE_NAME"])["Role"]["Arn"]
ip = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=15).read().decode().strip()
import ipaddress
ipaddress.IPv4Address(ip)
bucket = f"ray-assignment-{expected}-{region}-state"
common = dict(region=region, expected_account_id=expected)
data_settings_path = root / "infra" / "data" / "terraform.tfvars.json"
previous_data = json.loads(data_settings_path.read_text()) if data_settings_path.exists() else {}
compute_settings_path = root / "infra" / "compute" / "terraform.tfvars.json"
previous_compute = json.loads(compute_settings_path.read_text()) if compute_settings_path.exists() else {}
lease = os.getenv("LEASE_EXPIRES_AT") or previous_compute.get("lease_expires_at") or (
    datetime.now(timezone.utc) + timedelta(hours=8)
).strftime("%Y-%m-%dT%H:%M:%SZ")
settings = {
    "bootstrap": common,
    "data": {**common, "budget_alert_email": os.getenv("BUDGET_ALERT_EMAIL", previous_data.get("budget_alert_email"))},
    "compute": {**common, "state_bucket": bucket, "admin_principal_arn": role,
                "admin_cidrs": [ip + "/32"],
                "lease_expires_at": lease},
    "platform": {**common, "state_bucket": bucket},
}
for layer, values in settings.items():
    folder = root / "infra" / layer
    (folder / "terraform.tfvars.json").write_text(json.dumps(values, indent=2) + "\n")
    if layer != "bootstrap":
        (folder / "backend.hcl").write_text(
            f'bucket = "{bucket}"\nkey = "{layer}/terraform.tfstate"\nregion = "{region}"\nencrypt = true\nuse_lockfile = true\n')
print(json.dumps({"account": expected, "region": region, "profile": os.environ["AWS_PROFILE"],
                  "lease_expires_at": settings["compute"]["lease_expires_at"]}, indent=2))
