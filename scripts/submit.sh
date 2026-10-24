#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
# SQLite profile permits only one active pipeline writer.
active=$(kubectl --context kind-ray-assignment -n ray-assignment get rayjobs -o json | python3 -c 'import json,sys; print(sum(j.get("status",{}).get("jobDeploymentStatus") not in ("Complete","Failed") for j in json.load(sys.stdin)["items"]))')
if [ "$active" != 0 ]; then
  echo 'An unfinished RayJob exists; inspect it before submitting another.' >&2
  exit 1
fi
kubectl --context kind-ray-assignment create -f k8s/rayjob.yaml
