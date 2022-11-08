"""Unit tests for reaper.azure_power_off_vms."""
from unittest.mock import Mock, patch
import uuid

import reaper.azure_power_off_vms


def synthesize_resource_id(
    subscription_id=None,
    resource_group=None,
    resource_provider=None,
    resource_type=None,
    resource_id=None,
):
    """
    Synthesize a pseudorandom resource ID.

    Defaults assume this should look like a Compute Virtual Machine's ID.
    """
    return (
        f"/subscriptions/{subscription_id if subscription_id else uuid.uuid4()}"
        f"/resourceGroups/{resource_group if resource_group else uuid.uuid4()}"
        f"/providers/{resource_provider if resource_provider else 'Microsoft.Compute'}"
        f"/{resource_type if resource_type else 'virtualMachines'}"
        f"/{resource_id if resource_id else uuid.uuid4()}"
    )


def synthesize_tags(with_bypass_tag=True):
    """Synthesize a set of pseudorandom tags for a resource."""
    conditional_tag_key = (
        reaper.azure_power_off_vms.REAP_BYPASS_TAG
        if with_bypass_tag
        else str(uuid.uuid4())
    )
    tags = {
        str(uuid.uuid4()): str(uuid.uuid4()),
        conditional_tag_key: str(uuid.uuid4()),
        str(uuid.uuid4()): str(uuid.uuid4()),
    }
    return tags


def create_mock_resource(
    name=None,
    resource_id=None,
    resource_group=None,
    resource_provider=None,
    resource_type=None,
    is_running=True,
    tags=None,
    include_statuses=False,
):
    """
    Create a Mock object that looks like an Azure Resource.

    Defaults assume this should look like a Compute Virtual Machine.
    """
    mock_resource = Mock()
    mock_resource.name = name if name else str(uuid.uuid4())
    mock_resource.id = (
        resource_id
        if resource_id
        else synthesize_resource_id(
            resource_group=resource_group,
            resource_provider=resource_provider,
            resource_type=resource_type,
        )
    )
    if include_statuses:
        mock_unrelated_status = Mock()
        mock_unrelated_status.code = "unrelated/status"
        mock_running_status = Mock()
        mock_running_status.code = (
            "PowerState/running" if is_running else "PowerState/off"
        )
        mock_another_status = Mock()
        mock_another_status.code = "another/status"

        mock_resource.instance_view.statuses = [
            mock_unrelated_status,
            mock_running_status,
            mock_another_status,
        ]
    mock_resource.tags = tags if tags else None
    return mock_resource


@patch("reaper.azure_power_off_vms.EnvironmentCredential")
@patch("reaper.azure_power_off_vms.ComputeManagementClient")
def test_get_azure_compute_client(mock_compute_class, mock_environment_class):
    """Test getting a ComputeManagementClient for the given Azure subscription ID."""
    azure_subscription_id = str(uuid.uuid4())
    client = reaper.azure_power_off_vms.get_azure_compute_client(azure_subscription_id)
    mock_environment_class.assert_called()
    mock_compute_class.assert_called_once_with(
        mock_environment_class.return_value, azure_subscription_id
    )
    assert client == mock_compute_class.return_value


def test_vm_is_running():
    """Test vm_is_running correctly identifies running VMs."""
    mock_vm = create_mock_resource(is_running=True, include_statuses=True)
    assert reaper.azure_power_off_vms.vm_is_running(mock_vm) is True
    mock_vm = create_mock_resource(is_running=False, include_statuses=True)
    assert reaper.azure_power_off_vms.vm_is_running(mock_vm) is False


def test_has_bypass_tag():
    """Test has_bypass_tag correctly identifies VMs with the bypass tag."""
    tags_with_bypass = synthesize_tags(with_bypass_tag=True)
    mock_vm = create_mock_resource(tags=tags_with_bypass, include_statuses=False)
    assert reaper.azure_power_off_vms.has_bypass_tag(mock_vm) is True

    tags_without_bypass = synthesize_tags(with_bypass_tag=False)
    mock_vm = create_mock_resource(tags=tags_without_bypass, include_statuses=False)
    assert reaper.azure_power_off_vms.has_bypass_tag(mock_vm) is False

    mock_vm = create_mock_resource(tags={}, include_statuses=False)
    assert reaper.azure_power_off_vms.has_bypass_tag(mock_vm) is False

    mock_vm = create_mock_resource(tags=None, include_statuses=False)
    assert reaper.azure_power_off_vms.has_bypass_tag(mock_vm) is False


def test_get_resource_group_name():
    """Test get_resource_group_name correctly extracts the resource group name."""
    resource_group = str(uuid.uuid4())
    mock_vm = create_mock_resource(resource_group=resource_group)
    assert reaper.azure_power_off_vms.get_resource_group_name(mock_vm) == resource_group


def test_power_off_vm():
    """Test power_off_vm correctly uses the client to power off the VM."""
    name = str(uuid.uuid4())
    resource_group = str(uuid.uuid4())
    mock_vm = create_mock_resource(name=name, resource_group=resource_group)
    mock_client = Mock()

    reaper.azure_power_off_vms.power_off_vm(mock_client, mock_vm)
    mock_client.virtual_machines.begin_power_off.assert_called_once_with(
        resource_group, name
    )


def test_get_vms():
    """
    Test get_vms correctly retrieves all regular VMs with combined metadata.

    This test defines two VMs, one with the bypass tag and one without, but because
    we have to make two Azure calls and combine results, there are four calls to
    create_mock_resource. "mock_vm_0_id" has the bypass tag. "mock_vm_1_id" does not.
    """
    mock_vm_0_id = synthesize_resource_id()
    mock_vm_0_with_tags_with_bypass = create_mock_resource(
        resource_id=mock_vm_0_id,
        tags=synthesize_tags(with_bypass_tag=True),
        include_statuses=False,
    )
    mock_vm_0_with_status = create_mock_resource(
        resource_id=mock_vm_0_id, is_running=True, include_statuses=True
    )

    mock_vm_1_id = synthesize_resource_id()
    mock_vm_1_with_tags_without_bypass = create_mock_resource(
        resource_id=mock_vm_1_id,
        tags=synthesize_tags(with_bypass_tag=False),
        include_statuses=False,
    )
    mock_vm_1_with_status = create_mock_resource(
        resource_id=mock_vm_1_id, is_running=True, include_statuses=True
    )

    mock_client = Mock()
    mock_client.virtual_machines.list_all.side_effect = [
        # The first `list_all` call gets the version with tags.
        [mock_vm_0_with_tags_with_bypass, mock_vm_1_with_tags_without_bypass],
        # The second `list_all` call gets the version with statuses.
        [mock_vm_0_with_status, mock_vm_1_with_status],
    ]
    vms = reaper.azure_power_off_vms.get_vms(mock_client)

    # These assertions verify that multiple `list_all` results were combined correctly.
    assert vms[0].id == mock_vm_0_id
    assert vms[0].tags == mock_vm_0_with_tags_with_bypass.tags
    assert vms[0].instance_view == mock_vm_0_with_status.instance_view
    assert vms[1].id == mock_vm_1_id
    assert vms[1].tags == mock_vm_1_with_tags_without_bypass.tags
    assert vms[1].instance_view == mock_vm_1_with_status.instance_view


def test_handle_regular_vms():
    """Test handle_regular_vms bypasses or powers off VMs correctly."""
    mock_vm_running_with_bypass = create_mock_resource(
        name="mock_vm_running_with_bypass",
        tags=synthesize_tags(with_bypass_tag=True),
        is_running=True,
        include_statuses=True,
    )
    mock_vm_running_resource_group = str(uuid.uuid4())
    mock_vm_running = create_mock_resource(
        name="mock_vm_running",
        resource_group=mock_vm_running_resource_group,
        is_running=True,
        include_statuses=True,
    )
    mock_vm_not_running = create_mock_resource(
        name="mock_vm_not_running", is_running=False, include_statuses=True
    )
    mock_vms = [mock_vm_running_with_bypass, mock_vm_running, mock_vm_not_running]

    mock_client = Mock()
    with patch.object(reaper.azure_power_off_vms, "get_vms") as mock_get_vms:
        mock_get_vms.return_value = mock_vms
        reaper.azure_power_off_vms.handle_regular_vms(mock_client)

    # Expect *only* mock_vm_running to be called to power off.
    # Others would be skipped either due to bypass flag or due to not running.
    mock_client.virtual_machines.begin_power_off.assert_called_once_with(
        mock_vm_running_resource_group, mock_vm_running.name
    )


def test_get_scale_sets():
    """Test get_scale_sets retrieves a list of Virtual Machine Scale Sets."""
    mock_client = Mock()
    scale_sets = reaper.azure_power_off_vms.get_scale_sets(mock_client)
    mock_client.virtual_machine_scale_sets.list_all.assert_called_once_with()
    assert scale_sets == mock_client.virtual_machine_scale_sets.list_all.return_value


def test_get_vms_for_scale_set():
    """Test get_vms_for_scale_set retrieves a list of VMs from the VM Scale Set."""
    mock_client = Mock()
    scale_set_name = str(uuid.uuid4())
    scale_set_resource_group = str(uuid.uuid4())
    mock_scale_set = create_mock_resource(
        resource_group=scale_set_resource_group, name=scale_set_name
    )

    vms = reaper.azure_power_off_vms.get_vms_for_scale_set(mock_client, mock_scale_set)

    mock_client.virtual_machine_scale_set_vms.list.assert_called_once_with(
        resource_group_name=scale_set_resource_group,
        virtual_machine_scale_set_name=scale_set_name,
        expand="instanceView",
    )
    assert vms == mock_client.virtual_machine_scale_set_vms.list.return_value


def test_power_off_scale_set_vm():
    """Test power_off_scale_set_vm correctly powers off the VMSS Virtual Machine."""
    mock_client = Mock()
    mock_scale_set = create_mock_resource()
    vm_resource_group = str(uuid.uuid4())
    mock_vm = create_mock_resource(resource_group=vm_resource_group)

    reaper.azure_power_off_vms.power_off_scale_set_vm(
        mock_client, mock_scale_set, mock_vm
    )

    mock_client.virtual_machine_scale_set_vms.begin_power_off(
        resource_group_name=vm_resource_group,
        vm_scale_set_name=mock_scale_set.name,
        instance_id=mock_vm.instance_id,
    )


def test_handle_scale_set_vms():
    """Test handle_scale_set_vms bypasses or powers off VMSS VMs correctly."""
    # This VMSS has bypass tag, and all its VMs should be skipped.
    mock_scale_set_with_bypass = create_mock_resource(
        tags=synthesize_tags(with_bypass_tag=True)
    )

    # VMSS has no bypass tag. Its VMS should be checked.
    mock_scale_set = create_mock_resource()
    # First VM is running but has bypass tag. It should be skipped.
    mock_vm_running_with_bypass = create_mock_resource(
        name="mock_vm_running_with_bypass",
        tags=synthesize_tags(with_bypass_tag=True),
        is_running=True,
        include_statuses=True,
    )
    # Second VM is running but does not have bypass tag. It should be powered off.
    mock_vm_running = create_mock_resource(
        name="mock_vm_running",
        is_running=True,
        include_statuses=True,
    )
    # Third VM is not running. It should be skipped.
    mock_vm_not_running = create_mock_resource(
        name="mock_vm_not_running", is_running=False, include_statuses=True
    )
    mock_vms = [mock_vm_running_with_bypass, mock_vm_running, mock_vm_not_running]

    mock_client = Mock()
    with patch.object(
        reaper.azure_power_off_vms, "get_scale_sets"
    ) as mock_get_scale_sets, patch.object(
        reaper.azure_power_off_vms, "get_vms_for_scale_set"
    ) as mock_get_vms_for_scale_set, patch.object(
        reaper.azure_power_off_vms, "power_off_scale_set_vm"
    ) as mock_power_off_scale_set_vm:
        mock_get_scale_sets.return_value = [mock_scale_set_with_bypass, mock_scale_set]
        mock_get_vms_for_scale_set.side_effect = [mock_vms]
        reaper.azure_power_off_vms.handle_scale_set_vms(mock_client)

        # power_off_scale_set_vm should be called only once for the one untagged and
        # powered VM in the second VMSS. The first VMSS should be skipped entirely due
        # to its bypass tag, and the other VMs in the second VMSS either have the bypass
        # tag or are not powered on.
        mock_power_off_scale_set_vm.assert_called_once_with(
            mock_client, mock_scale_set, mock_vm_running
        )
