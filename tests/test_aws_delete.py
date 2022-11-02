"""Unit tests for reaper.aws_delete."""
import datetime
from unittest.mock import Mock, call, patch

from botocore.exceptions import ClientError

import reaper.aws_delete


@patch("reaper.aws_delete.boto3")
def test_get_account(mock_boto3):
    """Test getting the current active AWS account."""
    expected_account = "123456789"
    fake_response = {"Account": expected_account}
    mock_boto3.client.return_value.get_caller_identity.return_value = fake_response
    account = reaper.aws_delete.get_account()
    assert account == expected_account


@patch("reaper.aws_delete.boto3")
def test_get_region_names(mock_boto3):
    """Test getting a list of all available region names."""
    expected_regions = ["hello", "world"]
    fake_response = {"Regions": [{"RegionName": name} for name in expected_regions]}
    mock_boto3.client.return_value.describe_regions.return_value = fake_response
    regions = reaper.aws_delete.get_region_names()
    assert regions == expected_regions


def test_has_bypass_tag_found():
    """Test test_has_bypass_tag finds the bypass tag."""
    resource = {
        "Tags": [
            {"Key": "potato", "Value": "gems"},
            {"Key": reaper.aws_delete.REAP_BYPASS_TAG, "Value": "precious"},
        ]
    }
    assert reaper.aws_delete.has_bypass_tag(resource)


def test_has_bypass_tag_no_tags():
    """Test test_has_bypass_tag is False with no tags."""
    resource = {"hello": "world"}
    assert not reaper.aws_delete.has_bypass_tag(resource)


def test_has_bypass_tag_not_found():
    """Test test_has_bypass_tag is False with tags but not the bypass tag."""
    resource = {
        "Tags": [
            {"Key": "potato", "Value": "gems"},
            {"Key": "taters", "Value": "precious"},
        ]
    }
    assert not reaper.aws_delete.has_bypass_tag(resource)


@patch("reaper.aws_delete.delete_volume")
@patch("reaper.aws_delete.describe_volumes_to_delete")
@patch("reaper.aws_delete.logger")
def test_delete_old_volumes(mock_logger, mock_describe, mock_delete):
    """Test delete_old_volumes typical behavior."""
    ec2_client = Mock()
    fake_volumes = [{"Size": "5"}, {"Size": "1"}, {}]
    mock_describe.return_value = fake_volumes

    total_count, total_size = reaper.aws_delete.delete_old_volumes(ec2_client, Mock())

    assert total_count == 3
    assert total_size == 6
    expected_delete_calls = [call(ec2_client, volume) for volume in fake_volumes]
    mock_delete.assert_has_calls(expected_delete_calls)
    expected_info_calls = [call("Found %s volumes having total %s GB", 3, 6.0)]
    mock_logger.info.assert_has_calls(expected_info_calls)


@patch("reaper.aws_delete.delete_volume")
@patch("reaper.aws_delete.describe_volumes_to_delete")
def test_delete_old_volumes_exception(mock_describe, mock_delete):
    """Test delete_old_volumes handles unexpected failures."""
    ec2_client = Mock()
    fake_volumes = [{"Size": "5"}, {"Size": "1"}, {}]
    mock_describe.return_value = fake_volumes
    client_error = ClientError(
        error_response={"Error": {"Code": "UnknownError"}},
        operation_name=Mock(),
    )
    mock_delete.side_effect = [True, client_error, True]

    total_count, total_size = reaper.aws_delete.delete_old_volumes(ec2_client, Mock())

    assert total_count == 2  # because the second one failed
    assert total_size == 5  # because the second one failed
    expected_delete_calls = [call(ec2_client, volume) for volume in fake_volumes]
    mock_delete.assert_has_calls(expected_delete_calls)


def test_describe_volumes_to_delete():
    """Test describe_volumes_to_delete filters described results as expected."""
    oldest_allowed = datetime.datetime(2020, 10, 26, 12, 34, 56)
    older = datetime.datetime(2020, 10, 26, 10, 0, 0)
    younger = datetime.datetime(2020, 10, 26, 13, 0, 0)
    fake_response = {
        "Volumes": [
            {"CreateTime": older},  # ready to delete
            {"CreateTime": older, "Attachments": []},  # ready to delete
            {"CreateTime": older, "Attachments": ["some-value"]},
            {"CreateTime": older, "Tags": [{"Key": reaper.aws_delete.REAP_BYPASS_TAG}]},
            {"CreateTime": oldest_allowed},
            {"CreateTime": younger},
        ]
    }
    expected_volumes = fake_response["Volumes"][:2]  # first two are ready to delete
    ec2_client = Mock()
    ec2_client.describe_volumes.return_value = fake_response

    volumes = reaper.aws_delete.describe_volumes_to_delete(ec2_client, oldest_allowed)

    assert volumes == expected_volumes


@patch("reaper.aws_delete.delete_snapshot")
@patch("reaper.aws_delete.describe_snapshots_to_delete")
@patch("reaper.aws_delete.logger")
def test_delete_old_snapshots(mock_logger, mock_describe, mock_delete):
    """Test delete_old_snapshots typical behavior."""
    ec2_client = Mock()
    fake_snapshots = [{"VolumeSize": "5"}, {"VolumeSize": "1"}, {}]
    mock_describe.return_value = fake_snapshots

    total_count, total_size = reaper.aws_delete.delete_old_snapshots(
        ec2_client, Mock(), Mock()
    )

    assert total_count == 3
    assert total_size == 6
    expected_delete_calls = [call(ec2_client, snapshot) for snapshot in fake_snapshots]
    mock_delete.assert_has_calls(expected_delete_calls)

    expected_info_calls = [call("Found %s snapshots having total %s GB", 3, 6.0)]
    mock_logger.info.assert_has_calls(expected_info_calls)


@patch("reaper.aws_delete.delete_snapshot")
@patch("reaper.aws_delete.describe_snapshots_to_delete")
def test_delete_old_snapshots_exception(mock_describe, mock_delete):
    """Test delete_old_snapshots handles unexpected failures."""
    ec2_client = Mock()
    fake_snapshots = [{"VolumeSize": "5"}, {"VolumeSize": "1"}, {}]
    mock_describe.return_value = fake_snapshots
    client_error = ClientError(
        error_response={"Error": {"Code": "UnknownError"}},
        operation_name=Mock(),
    )
    mock_delete.side_effect = [True, client_error, True]

    total_count, total_size = reaper.aws_delete.delete_old_snapshots(
        ec2_client, Mock(), Mock()
    )

    assert total_count == 2  # because the second one failed
    assert total_size == 5  # because the second one failed
    expected_delete_calls = [call(ec2_client, snapshot) for snapshot in fake_snapshots]
    mock_delete.assert_has_calls(expected_delete_calls)


def test_describe_snapshots_to_delete():
    """Test describe_snapshots_to_delete filters described results as expected."""
    oldest_allowed = datetime.datetime(2020, 10, 26, 12, 34, 56)
    older = datetime.datetime(2020, 10, 26, 10, 0, 0)
    younger = datetime.datetime(2020, 10, 26, 13, 0, 0)
    fake_response = {
        "Snapshots": [
            {"StartTime": older},  # ready to delete
            {"StartTime": older},  # ready to delete
            {"StartTime": older, "Tags": [{"Key": reaper.aws_delete.REAP_BYPASS_TAG}]},
            {"StartTime": oldest_allowed},
            {"StartTime": younger},
        ]
    }
    expected_snapshots = fake_response["Snapshots"][:2]  # first two are ready to delete
    ec2_client = Mock()
    ec2_client.describe_snapshots.return_value = fake_response

    volumes = reaper.aws_delete.describe_snapshots_to_delete(
        ec2_client, Mock(), oldest_allowed
    )

    assert volumes == expected_snapshots


@patch("reaper.aws_delete.delete_old_snapshots")
@patch("reaper.aws_delete.delete_old_volumes")
@patch("reaper.aws_delete.boto3")
@patch("reaper.aws_delete.get_region_names")
@patch("reaper.aws_delete.get_now")
@patch("reaper.aws_delete.get_account")
@patch("reaper.aws_delete.logger")
def test_reap(
    mock_logger,
    mock_get_account,
    mock_get_now,
    mock_get_region_names,
    mock_boto3,
    mock_delete_old_volumes,
    mock_delete_old_snapshots,
):
    """Test the main reap function typical behavior."""
    fake_regions = ["region-1", "region-2"]
    mock_get_region_names.return_value = fake_regions
    mock_delete_old_volumes.return_value = (2, 3)
    mock_delete_old_snapshots.return_value = (4, 5)
    expected_info_calls = [
        call("Checking region-1"),
        call("Checking region-2"),
        call("Deleted 4 volumes having total 6.0 GB"),
        call("Deleted 8 snapshots having total 10.0 GB"),
    ]

    reaper.aws_delete.reap()

    assert len(mock_delete_old_volumes.mock_calls) == len(fake_regions)
    assert len(mock_delete_old_snapshots.mock_calls) == len(fake_regions)
    mock_logger.info.assert_has_calls(expected_info_calls)
