#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
# Hard-coded local context deliberately prevents accidental cloud changes.
context=kind-ray-assignment
mkdir -p runtime
umask 077
if ! kubectl --context "$context" -n ray-assignment get secret ray-grafana-admin >/dev/null 2>&1; then
  python3 -c 'import secrets; from pathlib import Path; Path("runtime/grafana-password").write_text(secrets.token_urlsafe(32))'
  kubectl --context "$context" -n ray-assignment create secret generic ray-grafana-admin \
    --from-file=password=runtime/grafana-password
fi
helm upgrade --install ray-observability charts/observability \
  --kube-context "$context" --namespace ray-assignment \
  --set grafana.enabled=true --set logging.enabled=false --wait --atomic --timeout 300s
printf 'Grafana: http://127.0.0.1:3000/d/ray-assignment\nUser: admin\nPassword: runtime/grafana-password (private file)\nKeep this terminal running; Ctrl-C closes access.\n'
exec kubectl --context "$context" -n ray-assignment port-forward --address 127.0.0.1 service/ray-grafana 3000:3000
