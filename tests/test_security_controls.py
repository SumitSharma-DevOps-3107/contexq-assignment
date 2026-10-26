import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('title,expected', [
    ('security(ci): enforce reviewed deployments', True),
    ('fix: update configuration safely', True),
    ('quick fix', False), ('fix: x', False),
    ('fix: ' + 'x' * 80, False), ('fix: newline\ninjection', False),
])
def test_title_validation(title, expected):
    assert load('check-title').valid(title) is expected

@pytest.mark.parametrize('report', [{}, {'SchemaVersion': 2, 'Results': []}])
def test_empty_scans_fail_closed(report):
    with pytest.raises(ValueError):
        load('security-scan').summarize(report)

def test_plan_summary_does_not_publish_resource_values():
    result = load('security-scan').summarize({'SchemaVersion': 2, 'Results': [{
        'Target': 'private-path', 'Misconfigurations': [{
            'ID': 'AWS-0104', 'Severity': 'CRITICAL', 'Status': 'FAIL',
            'Title': 'Unrestricted egress', 'Resolution': 'Restrict destinations',
            'PrimaryURL': 'https://avd.aquasec.com/misconfig/aws-0104',
            'Message': 'private-resource-value', 'CauseMetadata': {'Code': 'secret'},
        }],
    }]})
    assert len(result) == 1
    assert 'private' not in str(result) and 'secret' not in str(result)
    assert result[0]['Resolution'] == 'Restrict destinations'

def exception_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return load('security_exception')


def test_egress_exception_expires_and_cannot_cover_other_resources(monkeypatch):
    from datetime import datetime, timezone
    m = exception_module(monkeypatch)
    item = {'ID': 'AWS-0104', 'CauseMetadata': {'Resource': 'aws_security_group.runner'}}
    result = {'Target': 'ci/main.tf'}
    assert m.permitted(result, item, ROOT / 'infra', now=datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert not m.permitted(result, item, ROOT / 'infra', now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert not m.permitted({'Target': 'other/main.tf'}, item, ROOT / 'infra')
    assert not m.permitted(result, {**item, 'ID': 'AWS-0040'}, ROOT / 'infra')


@pytest.mark.parametrize('port,ingress,layer,expected', [(443, [], 'ci', True), (80, [], 'ci', False), (443, [{}], 'ci', False), (443, [], 'compute', False)])
def test_resolved_plan_exception_checks_actual_ports_and_ingress(monkeypatch, tmp_path, port, ingress, layer, expected):
    import json
    from datetime import datetime, timezone
    m = exception_module(monkeypatch)
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'planned_values': {'root_module': {'resources': [{
        'address': 'aws_security_group.runner', 'values': {'ingress': ingress, 'egress': [{
            'from_port': port, 'to_port': port, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']
        }]}
    }]}}}))
    item = {'ID': 'AWS-0104', 'CauseMetadata': {'Resource': 'aws_security_group.runner'}}
    assert m.permitted({}, item, plan, layer, datetime(2026, 10, 25, tzinfo=timezone.utc)) is expected
