#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools:$PATH"
# Synthetic rule inputs; does not disrupt a real Ray workload or notify anyone.
tar -cf - tests/alerts.test.yml charts/observability/files/alerts.yml |
  kubectl --context kind-ray-assignment -n ray-assignment exec -i deployment/ray-prometheus -- sh -c '
    set -eu
    test_dir=$(mktemp -d /prometheus/.alert-tests.XXXXXX)
    trap "rm -rf \"$test_dir\"" EXIT
    export TMPDIR="$test_dir"
    cd "$test_dir"
    tar -xf -
    promtool test rules tests/alerts.test.yml
  '
