"""Fail-closed ECR scan gate and immutable promotion of one ARM64 image digest."""
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from ci_common import aws


def check_scan(scan, now=None):
    if scan.get('imageScanStatus', {}).get('status') != 'COMPLETE':
        raise ValueError('Image scan is not complete')
    findings=scan.get('imageScanFindings', {})
    stamp=findings.get('imageScanCompletedAt')
    if not stamp:
        raise ValueError('Scan timestamp unavailable')
    age=((now or datetime.now(timezone.utc))-datetime.fromisoformat(stamp.replace('Z','+00:00'))).total_seconds()
    if age < -300 or age > 86400:
        raise ValueError('A scan completed within the last 24 hours is required')
    counts=findings.get('findingSeverityCounts')
    if not isinstance(counts,dict):
        raise ValueError('Scan severity counts unavailable')
    if any(int(counts.get(level,0)) for level in ('CRITICAL','HIGH','UNDEFINED')):
        raise ValueError('Critical, high, or undefined severity findings block golden promotion')
    return counts


def main():
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--digest',required=True)
    p.add_argument('--tag');p.add_argument('--check-only',action='store_true');args=p.parse_args()
    if args.repository!='ray-assignment' or not re.fullmatch(r'sha256:[a-f0-9]{64}',args.digest):
        raise SystemExit('Expected this assignment repository and an exact digest')
    if not args.check_only and not re.fullmatch(r'golden-[a-f0-9]{40}-[0-9]+-[0-9]+',args.tag or ''):
        raise SystemExit('Use an immutable golden-<commit>-<run>-<attempt> tag')
    expected=os.environ.get('EXPECTED_AWS_ACCOUNT_ID')
    if not expected or aws('sts','get-caller-identity')['Account']!=expected:
        raise SystemExit('Expected AWS account must be configured and match the caller')
    response=aws('ecr','batch-get-image','--repository-name',args.repository,'--image-ids','imageDigest='+args.digest)
    if response.get('failures') or len(response.get('images',[]))!=1:
        raise SystemExit('Exact image manifest unavailable')
    image=response['images'][0];manifest=json.loads(image['imageManifest']);scan_digest=args.digest
    if 'manifests' in manifest:
        platforms=[m for m in manifest['manifests'] if m.get('platform',{}).get('os')=='linux' and m.get('platform',{}).get('architecture')=='arm64']
        if any(m.get('platform',{}).get('architecture') not in ('arm64','unknown') for m in manifest['manifests']):
            raise SystemExit('Unscanned extra image platform is not allowed')
        if len(platforms)!=1: raise SystemExit('Expected exactly one Linux ARM64 image')
        scan_digest=platforms[0]['digest']
    scan=aws('ecr','describe-image-scan-findings','--repository-name',args.repository,'--image-id','imageDigest='+scan_digest)
    deadline=time.monotonic()+300
    while scan.get('imageScanStatus',{}).get('status') in ('IN_PROGRESS','PENDING') and time.monotonic()<deadline:
        time.sleep(10)
        scan=aws('ecr','describe-image-scan-findings','--repository-name',args.repository,'--image-id','imageDigest='+scan_digest)
    counts=check_scan(scan)
    if not args.check_only:
        Path('runtime').mkdir(exist_ok=True)
        Path('runtime/golden-manifest.json').write_text(image['imageManifest'])
        promoted=aws('ecr','put-image','--repository-name',args.repository,'--image-tag',args.tag,'--image-manifest','file://runtime/golden-manifest.json','--image-manifest-media-type',image['imageManifestMediaType'])
        if promoted['image']['imageId']['imageDigest']!=args.digest:
            raise RuntimeError('Promoted digest differs from verified input')
    print(json.dumps({'digest':args.digest,'scanned_platform_digest':scan_digest,'scan_counts':counts,'promoted':not args.check_only}))


if __name__=='__main__': main()
