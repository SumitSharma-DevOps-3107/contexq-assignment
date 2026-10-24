#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/aws-env.sh
account=$(aws sts get-caller-identity --query Account --output text)
[[ "$account" == "$EXPECTED_AWS_ACCOUNT_ID" ]] || { echo "Unexpected AWS account" >&2; exit 1; }
lease=$(terraform -chdir=infra/compute output -raw lease_expires_at)
.venv/bin/python - "$lease" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
deadline = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
if deadline - datetime.now(timezone.utc) < timedelta(minutes=30):
    raise SystemExit("Less than 30 minutes remain on the compute lease; do not submit a new job.")
PY
cluster=$(terraform -chdir=infra/compute output -raw cluster_name)
aws eks update-kubeconfig --name "$cluster" --kubeconfig runtime/eks-kubeconfig --alias ray-assignment-aws
.venv/bin/python scripts/render-aws-job.py
kubectl --kubeconfig runtime/eks-kubeconfig --context ray-assignment-aws create -f runtime/aws-rayjob.yaml
