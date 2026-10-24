import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from botocore.exceptions import ClientError

spec = importlib.util.spec_from_file_location("lease_guard", Path(__file__).parents[1] / "infra/compute/lease_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
CONFIG = {"expires_at": "2026-10-24T12:00:00Z", "cluster": "ray-assignment",
          "nat_id": "nat-example", "eip_allocation_id": "eipalloc-example"}


def missing():
    return ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "Gone"}}, "DescribeNodegroup")


def test_guard_does_nothing_before_deadline():
    eks, ec2 = Mock(), Mock()
    result = guard.reap(eks, ec2, CONFIG, datetime(2026, 10, 24, 11, tzinfo=timezone.utc))
    assert result["state"] == "within-lease"
    assert not eks.mock_calls and not ec2.mock_calls


def test_guard_deletes_only_named_groups_and_waits_for_cluster():
    eks, ec2 = Mock(), Mock()
    eks.describe_nodegroup.return_value = {"nodegroup": {"status": "ACTIVE"}}
    ec2.describe_nat_gateways.return_value = {"NatGateways": [{"State": "available"}]}
    guard.reap(eks, ec2, CONFIG, datetime(2026, 10, 24, 13, tzinfo=timezone.utc))
    assert [c.kwargs["nodegroupName"] for c in eks.delete_nodegroup.call_args_list] == ["workers", "system"]
    eks.delete_cluster.assert_not_called()
    ec2.delete_nat_gateway.assert_called_once_with(NatGatewayId="nat-example")
    ec2.release_address.assert_not_called()


def test_guard_finishes_cluster_and_eip_after_dependencies_are_gone():
    eks, ec2 = Mock(), Mock()
    eks.describe_nodegroup.side_effect = missing()
    eks.describe_cluster.return_value = {"cluster": {"status": "ACTIVE"}}
    ec2.describe_nat_gateways.return_value = {"NatGateways": [{"State": "deleted"}]}
    guard.reap(eks, ec2, CONFIG, datetime(2026, 10, 24, 13, tzinfo=timezone.utc))
    eks.delete_cluster.assert_called_once_with(name="ray-assignment")
    ec2.release_address.assert_called_once_with(AllocationId="eipalloc-example")


def test_guard_does_not_hide_access_denied():
    import pytest
    eks, ec2 = Mock(), Mock()
    eks.describe_nodegroup.side_effect = ClientError({"Error": {"Code": "AccessDeniedException"}}, "DescribeNodegroup")
    with pytest.raises(ClientError):
        guard.reap(eks, ec2, CONFIG, datetime(2026, 10, 24, 13, tzinfo=timezone.utc))
