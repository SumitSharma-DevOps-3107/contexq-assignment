#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
arch=$(docker info --format '{{.Architecture}}')
case "$arch" in
  aarch64|arm64) arch=aarch64 ;;
  x86_64|amd64) arch=x86_64 ;;
  *) echo 'Unsupported Docker architecture' >&2; exit 1 ;;
esac
mkdir -p .wheelhouse runtime
.venv/bin/python - <<'PY'
import tomllib
from pathlib import Path
deps = tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']
Path('runtime/image-requirements.txt').write_text('\n'.join(deps + ['setuptools==80.9.0', 'wheel==0.45.1']))
PY
.venv/bin/python -m pip download --dest .wheelhouse --only-binary=:all: \
  --python-version 311 --implementation cp --abi cp311 \
  --platform "manylinux2014_$arch" --platform "manylinux_2_17_$arch" \
  --platform "manylinux_2_24_$arch" --platform "manylinux_2_27_$arch" \
  --platform "manylinux_2_28_$arch" -r runtime/image-requirements.txt
