#!/usr/bin/env bash
set -euo pipefail
for tool in docker kind kubectl helm python3.11 make; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
docker info --format 'Docker: {{.ServerVersion}}; CPUs: {{.NCPU}}; memory bytes: {{.MemTotal}}; architecture: {{.Architecture}}'
python3.11 --version
kind version
kubectl version --client
helm version --short
echo 'Preflight passed. AWS credentials are not needed for local development.'
