"""Validate a concrete EKS encryption plan when Trivy loses nested provider blocks.

Never waive encryption: require every planned cluster to reference a known,
rotated, enabled KMS key in the same plan. Unknown values fail closed.
"""
import json
import re


def verified_eks_encryption(target, finding):
    if finding.get("ID") != "AWS-0039" or not target.is_file():
        return False
    try:
        plan = json.loads(target.read_text())
        resources = plan["resource_changes"]
        clusters = [r for r in resources if r["type"] == "aws_eks_cluster" and r["change"].get("after")]
        keys = {r["change"]["after"].get("arn"): r["change"] for r in resources
                if r["type"] == "aws_kms_key" and r["change"].get("after")}
        if not clusters:
            return False
        def unknown(value):
            if isinstance(value, dict):
                return any(unknown(v) for v in value.values())
            if isinstance(value, list):
                return any(unknown(v) for v in value)
            return value is True
        for cluster in clusters:
            change = cluster["change"]
            if unknown(change.get("after_unknown", {}).get("encryption_config", False)):
                return False
            encryption = change["after"]["encryption_config"]
            if len(encryption) != 1 or encryption[0]["resources"] != ["secrets"]:
                return False
            providers = encryption[0]["provider"]
            if len(providers) != 1:
                return False
            arn = providers[0]["key_arn"]
            if not re.fullmatch(r"arn:aws(?:-[a-z]+)?:kms:[a-z0-9-]+:[0-9]{12}:key/[a-f0-9-]{36}", arn):
                return False
            key = keys[arn]
            for field in ("enable_key_rotation", "is_enabled"):
                if key["after"].get(field) is not True or unknown(key.get("after_unknown", {}).get(field, False)):
                    return False
            if "delete" in key["actions"]:
                return False
        return True
    except (KeyError, TypeError, ValueError, OSError):
        return False
