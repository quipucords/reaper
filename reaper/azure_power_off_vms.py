"""Shut down running Azure VMs."""

import logging

from azure.identity import EnvironmentCredential
from azure.mgmt.compute import ComputeManagementClient
from envparse import env

logger = logging.getLogger(__name__)

REAP_BYPASS_TAG = env("REAP_BYPASS_TAG", default="do-not-delete")


def get_azure_compute_client(azure_subscription_id):
    """Get an Azure compute management client."""
    return ComputeManagementClient(EnvironmentCredential(), azure_subscription_id)


def vm_is_running(vm):
    """Return true if the vm specified has a PowerState/running state."""
    if vm and vm.instance_view:
        for status in vm.instance_view.statuses:
            if status.code == "PowerState/running":
                logger.info(f"Found running VM {vm.name}")
                return True
    return False


def has_bypass_tag(vm):
    """Return true if the VM has the configured bypass tag."""
    tags = getattr(vm, "tags", {})
    return tags is not None and REAP_BYPASS_TAG in tags


def get_resource_group_name(resource):
    """Get the resource group name for the given resource."""
    # This is ugly, but the easiest way to get the resource group is to
    # extract it from the resource's ID. A typical resource ID looks like:
    # /subscriptions/uuid/resourceGroups/rg-name/providers/...
    resource_group = resource.id.split("/")[4]
    return resource_group


def power_off_vm(compute_client, vm):
    """Power off the given VM."""
    resource_group = get_resource_group_name(vm)
    # Note: begin_power_off returns an LROPoller object that we could repeatedly
    # poll until the operation is done, but we don't need to monitor this here.
    # We can just discard the result and assume it completes.
    compute_client.virtual_machines.begin_power_off(resource_group, vm.name)


def get_vms(compute_client):
    """Get list of VMs with all the metadata we need."""
    vms_with_tags = compute_client.virtual_machines.list_all()
    vms_with_status = compute_client.virtual_machines.list_all(
        params={"statusOnly": "true"}
    )

    # list_all can't return all the data we need in one call.
    # vms_with_tags has the tags but no statuses.
    # vms_with_status has the statuses but no tags.
    # *sigh*
    # So, we iterate and merge them in this hacky way.
    vms_by_id = dict(((vm.id, vm) for vm in vms_with_tags))
    for vm in vms_with_status:
        vms_by_id[vm.id].instance_view = vm.instance_view
    return [vm for vm in vms_by_id.values()]


def handle_regular_vms(compute_client):
    """Identify and conditionally power off regular VMs."""
    vms = get_vms(compute_client)
    for vm in vms:
        if has_bypass_tag(vm):
            logger.info(f"VM {vm.name} has bypass tag and will not be powered off.")
            continue
        if vm_is_running(vm):
            logger.info(f"Attempting to power off VM {vm.name}")
            power_off_vm(compute_client, vm)


def get_scale_sets(compute_client):
    """Get iterator of all VM scale sets."""
    scale_sets = compute_client.virtual_machine_scale_sets.list_all()
    return scale_sets


def get_vms_for_scale_set(compute_client, scale_set):
    """Get iterator of all VMs in the given VM scale set."""
    resource_group = get_resource_group_name(scale_set)
    vms = compute_client.virtual_machine_scale_set_vms.list(
        resource_group_name=resource_group,
        virtual_machine_scale_set_name=scale_set.name,
        expand="instanceView",
    )
    return vms


def power_off_scale_set_vm(compute_client, scale_set, vm):
    """Power off the given VM belonging to the given scale set."""
    resource_group = get_resource_group_name(vm)
    # Note: begin_power_off returns an LROPoller object that we could repeatedly
    # poll until the operation is done, but we don't need to monitor this here.
    # We can just discard the result and assume it completes.
    compute_client.virtual_machine_scale_set_vms.begin_power_off(
        resource_group_name=resource_group,
        vm_scale_set_name=scale_set.name,
        instance_id=vm.instance_id,
    )


def handle_scale_set_vms(compute_client):
    """Identify and conditionally power off VM scale set VMs."""
    scale_sets = get_scale_sets(compute_client)
    for scale_set in scale_sets:
        if has_bypass_tag(scale_set):
            logger.info(
                f"VM scale set {scale_set.name} has bypass tag "
                "and will not be powered off."
            )
            continue
        vms = get_vms_for_scale_set(compute_client, scale_set)
        for vm in vms:
            if has_bypass_tag(vm):
                logger.info(
                    f"VM scale set VM {vm.name} has bypass tag "
                    "and will not be powered off."
                )
                continue
            if vm_is_running(vm):
                logger.info(f"Attempting to power off VM scale set VM {vm.name}")
                power_off_scale_set_vm(compute_client, scale_set, vm)


def reap():
    """Power off all running VMs."""
    logger.info("Preparing to power off Azure VMs.")
    azure_subscription_id = env("AZURE_SUBSCRIPTION_ID")
    compute_client = get_azure_compute_client(azure_subscription_id)
    handle_regular_vms(compute_client)
    handle_scale_set_vms(compute_client)


if __name__ == "__main__":
    reap()
