#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/aws-env.sh
export KUBECONFIG="$PWD/runtime/eks-kubeconfig"
pod=$(kubectl -n ray-assignment get pods -l ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
[[ -n "$pod" ]] || { echo 'Start a RayJob first.' >&2; exit 1; }
echo 'Open http://127.0.0.1:8265 and enter the per-cluster token in the login dialog.'
echo 'Retrieve the token privately with the command in docs/observability.md; do not paste it into chat.'
exec kubectl -n ray-assignment port-forward --address 127.0.0.1 "pod/$pod" 8265:8265
