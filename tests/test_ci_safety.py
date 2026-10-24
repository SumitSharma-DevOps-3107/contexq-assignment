import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("ci_common", Path(__file__).parents[1] / "scripts/ci_common.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
NOW = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
CONFIG = {"account": "123456789012", "lease_expires_at": "2026-10-24T12:00:00Z", "repository_url": "123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/ray-assignment"}


def budget(amount="0", credits=False):
    return {"Budget": {"BudgetLimit": {"Unit": "USD", "Amount": "30"},
                       "CostTypes": {"IncludeCredit": credits, "IncludeRefund": False},
                       "CalculatedSpend": {"ActualSpend": {"Unit": "USD", "Amount": amount}}}}


def test_budget_accepts_active_low_cost_window(monkeypatch):
    monkeypatch.setattr(ci, "aws", lambda *args: budget("3.50"))
    assert ci.check_budget(CONFIG, NOW) == 3.5


@pytest.mark.parametrize("response", [budget("20"), budget("1", credits=True), {"Budget": {"BudgetLimit": {"Unit": "USD", "Amount": "30"}, "CostTypes": {"IncludeCredit": False, "IncludeRefund": False}}}])
def test_budget_fails_closed_for_spend_credits_or_missing_usage(monkeypatch, response):
    monkeypatch.setattr(ci, "aws", lambda *args: response)
    with pytest.raises(ValueError):
        ci.check_budget(CONFIG, NOW)


def test_expiring_lease_stops_before_any_api_call(monkeypatch):
    monkeypatch.setattr(ci, "aws", lambda *args: pytest.fail("Must reject before AWS calls"))
    with pytest.raises(ValueError, match="30 minutes"):
        ci.check_budget({**CONFIG, "lease_expires_at": "2026-10-24T10:20:00Z"}, NOW)


def test_deploy_accepts_only_own_repository_digest():
    image = CONFIG["repository_url"] + "@sha256:" + "a" * 64
    assert ci.image_uri(CONFIG, image) == image
    for invalid in (CONFIG["repository_url"] + ":latest", image.replace("123456789012", "999999999999"), image + "suffix"):
        with pytest.raises(ValueError):
            ci.image_uri(CONFIG, invalid)
