#!/usr/bin/env bash
set -euo pipefail
umask 077
# This script and its Python helpers must be baked into the reviewed server image.
# Never substitute a script path from the checked-out PR.
mkdir -p runtime
trap 'rm -f runtime/atlantis-private.log runtime/ci-environment.json runtime/private-codebuild-result.json' EXIT
if ! python3 /opt/atlantis/ci-trigger.py plan > runtime/atlantis-private.log 2>&1; then
  echo 'Private plan failed. An owner must inspect CodeBuild logs; no raw plan is published.'
  exit 1
fi
python3 - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('runtime/plan-result.json').read_text())
print('Terraform plans (no apply):')
for layer in ('bootstrap','data','compute','ci','platform'):
    result=r['layers'][layer]
    code=int(result['exit_code'])
    if code not in (0,2): raise SystemExit('Plan failed')
    print(f"- {layer}: {'changes proposed' if code==2 else 'no changes'}")
print('Detailed plans are private in S3 with one-day retention. No saved plan can be applied by this server.')
PY
