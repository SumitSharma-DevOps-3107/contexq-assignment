import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).parents[1]


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('promote_image', ROOT/'scripts/promote-image.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('counts', [{'CRITICAL':1},{'HIGH':1},{'UNDEFINED':1}])
def test_golden_gate_rejects_serious_findings(monkeypatch, counts):
    m=module(monkeypatch)
    with pytest.raises(ValueError,match='block golden'):
        m.check_scan({'imageScanStatus':{'status':'COMPLETE'},'imageScanFindings':{'imageScanCompletedAt':'2026-10-24T12:00:00Z','findingSeverityCounts':counts}}, datetime(2026,10,24,13,tzinfo=timezone.utc))


def test_golden_gate_rejects_missing_or_stale_results(monkeypatch):
    m=module(monkeypatch)
    for scan in ({}, {'imageScanStatus':{'status':'COMPLETE'}}, {'imageScanStatus':{'status':'COMPLETE'},'imageScanFindings':{'imageScanCompletedAt':'2026-10-20T12:00:00Z','findingSeverityCounts':{}}}):
        with pytest.raises(ValueError):m.check_scan(scan,datetime(2026,10,24,13,tzinfo=timezone.utc))


def test_golden_gate_accepts_fresh_nonblocking_scan(monkeypatch):
    m=module(monkeypatch)
    assert m.check_scan({'imageScanStatus':{'status':'COMPLETE'},'imageScanFindings':{'imageScanCompletedAt':'2026-10-24T12:00:00Z','findingSeverityCounts':{'LOW':2}}},datetime(2026,10,24,13,tzinfo=timezone.utc))=={'LOW':2}


def test_atlantis_denies_apply_forks_and_repo_workflow_override():
    s=yaml.safe_load((ROOT/'deploy/atlantis/server.yaml').read_text())
    assert set(s['allow-commands'].split(','))=={'plan','version','unlock','cancel'}
    assert s['allow-fork-prs'] is False and s['disable-autoplan'] is True
    r=yaml.safe_load((ROOT/'deploy/atlantis/repos.yaml').read_text())['repos'][0]
    assert r['allow_custom_workflows'] is False and r['allowed_overrides']==[]
    assert 'approved' in r['plan_requirements']
