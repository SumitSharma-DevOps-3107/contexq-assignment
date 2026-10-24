#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
mkdir -p runtime/kubernetes
# This is a synthetic-data-only bind mount for the non-root container user.
chmod 777 runtime/kubernetes
python3 - <<'PY'
import json
from pathlib import Path
config = {"kind": "Cluster", "apiVersion": "kind.x-k8s.io/v1alpha4", "nodes": [
    {"role": "control-plane", "labels": {"assignment-pool": "system"},
     "extraMounts": [{"hostPath": str(Path("runtime/kubernetes").resolve()),
                      "containerPath": "/assignment-output"}]},
    {"role": "worker", "labels": {"assignment-pool": "workers"}}]}
Path("runtime/kind.json").write_text(json.dumps(config, indent=2))
PY
if ! kind get clusters | grep -qx ray-assignment; then
  kind create cluster --name ray-assignment --image kindest/node:v1.34.3 --config runtime/kind.json --wait 180s
fi
kubectl --context kind-ray-assignment create namespace ray-assignment --dry-run=client -o yaml | kubectl --context kind-ray-assignment apply -f -
helm upgrade --install kuberay-operator kuberay-operator \
  --repo https://ray-project.github.io/kuberay-helm/ --version 1.5.1 \
  --kube-context kind-ray-assignment --namespace ray-assignment \
  -f k8s/operator-values.yaml --wait --timeout 180s
kind load docker-image ray-assignment:local --name ray-assignment
kubectl --context kind-ray-assignment -n ray-assignment get pods
