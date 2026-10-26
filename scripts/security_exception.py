"""One expiring, configuration-bound demo exception; never a global check ignore."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def runner_block(source):
    start = source.index('resource "aws_security_group" "runner" {')
    return source[start:source.index('\nresource ', start + 1)].strip()

def permitted(result, finding, target, layer=None, now=None):
    policy = json.loads((ROOT / 'security/egress-exception.json').read_text())
    now = now or datetime.now(timezone.utc)
    if now >= datetime.fromisoformat(policy['expires_at'].replace('Z', '+00:00')):
        return False
    if finding.get('ID') != 'AWS-0104' or finding.get('CauseMetadata', {}).get('Resource') != 'aws_security_group.runner':
        return False
    source = (ROOT / 'infra/ci/main.tf').read_text()
    if hashlib.sha256(runner_block(source).encode()).hexdigest() != policy['source_sha256']:
        return False
    if target.is_dir():
        return result.get('Target') == 'ci/main.tf' and target.resolve() == (ROOT / 'infra').resolve()
    if layer != 'ci':
        return False
    plan = json.loads(target.read_text())
    resources = plan.get('planned_values', {}).get('root_module', {}).get('resources', [])
    matches = [r for r in resources if r.get('address') == 'aws_security_group.runner']
    if len(matches) != 1:
        return False
    values = matches[0].get('values', {})
    egress = values.get('egress', [])
    if values.get('ingress') != [] or len(egress) != 1:
        return False
    rule = egress[0]
    return (rule.get('from_port') == 443 and rule.get('to_port') == 443
            and rule.get('protocol') == 'tcp' and rule.get('cidr_blocks') == ['0.0.0.0/0']
            and not rule.get('ipv6_cidr_blocks') and not rule.get('security_groups')
            and not rule.get('prefix_list_ids') and not rule.get('self'))
