#!/usr/bin/env python3
"""
Find and delete volumes and snapshots that we deem to be too old.

You might be a king or a little street sweeper,
but sooner or later you dance with the reaper.
"""
import datetime
import logging
from contextlib import contextmanager

import boto3
from botocore.exceptions import ClientError
from envparse import env


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(funcName)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

REAP_AGE_DEFAULT = 7 * 24 * 60 * 60  # one week in seconds
REAP_AGE_SNAPSHOTS = env.int("REAP_AGE_SNAPSHOTS", default=REAP_AGE_DEFAULT)
REAP_AGE_VOLUMES = env.int("REAP_AGE_VOLUMES", default=REAP_AGE_DEFAULT)
REAP_DRYRUN = env.bool("REAP_DRYRUN", default=False)
REAP_BYPASS_TAG = env("REAP_BYPASS_TAG", default="do-not-delete")


def get_account():
    """Get the current active AWS Account."""
    sts_client = boto3.client("sts")
    return sts_client.get_caller_identity()["Account"]


def get_region_names():
    """Get a list of all available region names."""
    ec2_client = boto3.client("ec2")
    regions = ec2_client.describe_regions()["Regions"]
    return [region["RegionName"] for region in regions]


def get_now():
    """Get the current time in UTC."""
    return datetime.datetime.now(datetime.timezone.utc)


@contextmanager
def handle_dryrun():
    """Gracefully handle possible DryRunOperation from boto3 calls."""
    try:
        yield
    except ClientError as e:
        error_code = e.response.get("Error").get("Code")
        if error_code == "DryRunOperation":
            logger.info("Skipping due to DryRunOperation")
        else:
            raise e


def has_bypass_tag(described_resource):
    """Check if the described resource has our reap bypass tag."""
    tags = described_resource.get("Tags", [])
    tag_keys = (tag.get("Key") for tag in tags)
    return REAP_BYPASS_TAG in tag_keys


def delete_old_volumes(ec2_client, oldest_allowed_volume_age):
    """Delete available volumes older than the allowed age."""
    total_count, total_size = 0, 0
    volumes = describe_volumes_to_delete(ec2_client, oldest_allowed_volume_age)
    for volume in volumes:
        try:
            delete_volume(ec2_client, volume)
            total_count += 1
            total_size += float(volume.get("Size", 0.0))
        except ClientError as e:
            error_code = e.response.get("Error").get("Code")
            if error_code == "InvalidVolume.NotFound":
                logger.info("Skipping because InvalidVolume.NotFound")
            else:
                logger.exception(e)
                logger.error("Failed to delete volume %s", volume)
    return total_count, total_size


def describe_volumes_to_delete(ec2_client, oldest_allowed):
    """
    Get a list of described volumes that meet the criteria for deletion.

    The volume must:
    - be older than allowed
    - be available
    - not be attached to any instances
    - not have the bypass tag
    """
    volumes = ec2_client.describe_volumes(
        # Yes, the described volume has "State", and the filter uses "status".
        # This mismatch is a mystery, but multiple experiments confirm this works.
        Filters=[{"Name": "status", "Values": ["available"]}]
    )
    volumes = [
        volume
        for volume in volumes["Volumes"]
        if volume["CreateTime"] < oldest_allowed
        and len(volume.get("Attachments", [])) == 0
        and not has_bypass_tag(volume)
    ]
    return volumes


@handle_dryrun()
def delete_volume(ec2_client, volume):
    """Delete the described volume."""
    logger.info(volume)
    logger.info(
        f"Deleting VolumeId {volume['VolumeId']} "
        f"(CreateTime='{volume['CreateTime']}' "
        f"Size={volume['Size']})"
    )
    ec2_client.delete_volume(VolumeId=volume["VolumeId"], DryRun=REAP_DRYRUN)


def delete_old_snapshots(ec2_client, account, oldest_allowed_snapshot_age):
    """Delete completed snapshots older than the allowed age."""
    total_count, total_size = 0, 0
    snapshots = describe_snapshots_to_delete(
        ec2_client, account, oldest_allowed_snapshot_age
    )
    for snapshot in snapshots:
        try:
            delete_snapshot(ec2_client, snapshot)
            total_count += 1
            total_size += float(snapshot.get("VolumeSize", 0.0))
        except ClientError as e:
            error_code = e.response.get("Error").get("Code")
            if error_code == "InvalidSnapshot.InUse":
                logger.info("Skipping because InvalidSnapshot.InUse")
            else:
                logger.exception(e)
                logger.error("Failed to delete snapshot %s", snapshot)
    return total_count, total_size


def describe_snapshots_to_delete(ec2_client, account, oldest_allowed):
    """
    Get a list of described snapshots that meet the criteria for deletion.

    The snapshot must:
    - be older than allowed
    - be completed
    - not have the bypass tag
    """
    snapshots = ec2_client.describe_snapshots(
        # Yes, the described snapshot has "State", and the filter uses "status".
        # This mismatch is a mystery, but multiple experiments confirm this works.
        Filters=[{"Name": "status", "Values": ["completed"]}],
        OwnerIds=[account],
    )
    snapshots = [
        snapshot
        for snapshot in snapshots["Snapshots"]
        if snapshot["StartTime"] < oldest_allowed and not has_bypass_tag(snapshot)
    ]
    return snapshots


@handle_dryrun()
def delete_snapshot(ec2_client, snapshot):
    """Delete the described snapshot."""
    logger.info(
        f"Deleting SnapshotId {snapshot['SnapshotId']} "
        f"(StartTime='{snapshot['StartTime']}' "
        f"VolumeSize={snapshot.get('VolumeSize')} "
        f"OwnerId={snapshot['OwnerId']})"
    )
    ec2_client.delete_snapshot(SnapshotId=snapshot["SnapshotId"], DryRun=REAP_DRYRUN)


def reap():
    """Iterate through all regions to delete old volumes and snapshots."""
    account = get_account()
    now = get_now()
    oldest_allowed_snapshot_age = now - datetime.timedelta(seconds=REAP_AGE_SNAPSHOTS)
    oldest_allowed_volume_age = now - datetime.timedelta(seconds=REAP_AGE_VOLUMES)

    total_volume_count = 0
    total_volume_size = 0.0
    total_snapshot_count = 0
    total_snapshot_size = 0.0

    logger.info(
        f"Finding volumes older than {oldest_allowed_volume_age} "
        f"({REAP_AGE_VOLUMES} seconds old)"
    )
    logger.info(
        f"Finding snapshots older than {oldest_allowed_snapshot_age} "
        f"({REAP_AGE_SNAPSHOTS} seconds old)"
    )
    try:
        for region_name in get_region_names():
            logger.info(f"Checking {region_name}")
            ec2_client = boto3.client("ec2", region_name=region_name)

            volume_count, volume_size = delete_old_volumes(
                ec2_client, oldest_allowed_volume_age
            )
            total_volume_count += volume_count
            total_volume_size += volume_size

            snapshot_count, snapshot_size = delete_old_snapshots(
                ec2_client, account, oldest_allowed_snapshot_age
            )
            total_snapshot_count += snapshot_count
            total_snapshot_size += snapshot_size
    except Exception as e:
        logger.exception(e)
        raise e
    finally:
        logger.info(
            f"Deleted {total_volume_count} volumes "
            f"having total {total_volume_size} GB"
        )
        logger.info(
            f"Deleted {total_snapshot_count} snapshots "
            f"having total {total_snapshot_size} GB"
        )


if __name__ == "__main__":
    reap()
