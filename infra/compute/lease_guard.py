"""Delete only the explicitly named demo compute/network resources after expiry."""
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def reap(eks, ec2, config, now):
    expiry = datetime.fromisoformat(config["expires_at"].replace("Z", "+00:00"))
    if now < expiry:
        return {"state": "within-lease", "expires_at": config["expires_at"]}
    remaining = False
    for name in ("workers", "system"):
        try:
            group = eks.describe_nodegroup(clusterName=config["cluster"], nodegroupName=name)["nodegroup"]
            remaining = True
            if group["status"] != "DELETING":
                eks.delete_nodegroup(clusterName=config["cluster"], nodegroupName=name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
    if not remaining:
        try:
            cluster = eks.describe_cluster(name=config["cluster"])["cluster"]
            if cluster["status"] != "DELETING":
                eks.delete_cluster(name=config["cluster"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
    try:
        gateways = ec2.describe_nat_gateways(NatGatewayIds=[config["nat_id"]])["NatGateways"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NatGatewayNotFound":
            raise
        gateways = []
    if gateways and gateways[0]["State"] not in ("deleted", "deleting"):
        ec2.delete_nat_gateway(NatGatewayId=config["nat_id"])
    if not gateways or gateways[0]["State"] == "deleted":
        try:
            ec2.release_address(AllocationId=config["eip_allocation_id"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "InvalidAllocationID.NotFound":
                raise
    return {"state": "cleanup-requested", "nodegroups_remaining": remaining}


def handler(event, context):
    result = reap(boto3.client("eks"), boto3.client("ec2"),
                  json.loads(os.environ["LEASE_CONFIG"]), datetime.now(timezone.utc))
    print(json.dumps(result))
    return result
