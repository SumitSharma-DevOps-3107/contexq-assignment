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
