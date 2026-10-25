import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from plan_encryption import verified_eks_encryption

ARN = "arn:aws:kms:ap-southeast-1:123456789012:key/11111111-1111-1111-1111-111111111111"
PLAN = {"resource_changes": [
    {"type": "aws_eks_cluster", "change": {"actions": ["create"], "after": {"encryption_config": [{"resources": ["secrets"], "provider": [{"key_arn": ARN}]}]}, "after_unknown": {"encryption_config": [{"provider": [{}], "resources": [False]}]}}},
    {"type": "aws_kms_key", "change": {"actions": ["no-op"], "after": {"arn": ARN, "enable_key_rotation": True, "is_enabled": True}, "after_unknown": {}}},
]}


def check(tmp_path, plan, finding="AWS-0039"):
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(plan))
    return verified_eks_encryption(target, {"ID": finding})


def test_concrete_encryption_with_empty_unknown_metadata(tmp_path):
    assert check(tmp_path, PLAN)
    assert not check(tmp_path, PLAN, "AWS-0104")


@pytest.mark.parametrize("case", ["unknown", "missing", "unrotated", "disabled", "replaced", "other_resource", "second_unencrypted"])
def test_unsafe_or_unverifiable_plans_fail_closed(tmp_path, case):
    p = copy.deepcopy(PLAN)
    cluster, key = [r["change"] for r in p["resource_changes"]]
    if case == "unknown":
        cluster["after_unknown"]["encryption_config"] = True
    elif case == "missing":
        cluster["after"].pop("encryption_config")
    elif case == "unrotated":
        key["after"]["enable_key_rotation"] = False
    elif case == "disabled":
        key["after"]["is_enabled"] = False
    elif case == "replaced":
        key["actions"] = ["delete", "create"]
    elif case == "other_resource":
        cluster["after"]["encryption_config"][0]["resources"] = ["configmaps"]
    else:
        p["resource_changes"].append({"type": "aws_eks_cluster", "change": {"actions": ["create"], "after": {"encryption_config": []}}})
    assert not check(tmp_path, p)
