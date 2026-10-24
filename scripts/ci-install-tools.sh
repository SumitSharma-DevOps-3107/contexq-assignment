#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .tools
if [[ "${1:-}" == terraform ]]; then
  case "$(uname -m)" in aarch64|arm64) arch=arm64;; x86_64) arch=amd64;; *) exit 1;; esac
  version=1.15.8
  archive="terraform_${version}_linux_${arch}.zip"
  base="https://releases.hashicorp.com/terraform/${version}"
  curl -fsSL --retry 2 "$base/$archive" -o ".tools/$archive"
  curl -fsSL --retry 2 "$base/terraform_${version}_SHA256SUMS" -o .tools/terraform-checksums
  python3 - "$archive" <<'PY'
import hashlib,sys,zipfile
from pathlib import Path
archive=sys.argv[1]
expected=next(line.split()[0] for line in Path('.tools/terraform-checksums').read_text().splitlines() if line.split()[-1]==archive)
assert hashlib.sha256(Path('.tools',archive).read_bytes()).hexdigest()==expected, 'Terraform checksum mismatch'
with zipfile.ZipFile(Path('.tools',archive)) as z:
    Path('.tools/terraform').write_bytes(z.read('terraform'))
Path('.tools/terraform').chmod(0o755)
PY
fi
