#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .tools
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) platform=darwin/arm64 ;;
  Linux-aarch64) platform=linux/arm64 ;;
  Linux-x86_64) platform=linux/amd64 ;;
  *) echo 'Unsupported platform for this helper' >&2; exit 1 ;;
esac
base="https://dl.k8s.io/release/v1.34.3/bin/$platform/kubectl"
curl -fsSL --retry 2 --max-time 120 "$base" -o .tools/kubectl.download
curl -fsSL --retry 2 --max-time 30 "$base.sha256" -o .tools/kubectl.sha256
python3 - <<'PY'
import hashlib
from pathlib import Path
p = Path('.tools/kubectl.download')
if hashlib.sha256(p.read_bytes()).hexdigest() != Path('.tools/kubectl.sha256').read_text().strip():
    raise SystemExit('kubectl checksum mismatch')
p.chmod(0o755)
p.replace('.tools/kubectl')
PY
