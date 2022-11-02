#!/usr/bin/env sh
# Carefully check autoscaling settings, and if the ECS cluster has been up
# for more than 30 minutes, set the scale to 0 and notify Slack.

# Important note:
# The ECS_CLUSTER_NAME variable does NOT have the cluster name.
# It has the cluster's AutoScalingGroup name instead.
# We should carefully rename it and update our GitLab variables.

alert_slack() {
    clean_message=$(echo "$1" | tr -d '"'"'") # remove any risky quotes
    curl_data='{"text":"'"${clean_message}"'"}'
    curl_header='Content-type: application/json'
    curl -X POST -H "${curl_header}" --data "${curl_data}" "${WEBHOOK_URL}"
}

fail() {
    message="$1"
    echo "${message}"
    alert_slack "${message}"
    exit 1
}

echo "Checking AutoScalingGroups name ${ECS_CLUSTER_NAME}"

desired_capacity=$(aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "${ECS_CLUSTER_NAME}" \
    --query "AutoScalingGroups[*].DesiredCapacity" \
    --output text)
if [ "${desired_capacity}" = "" ]; then
    fail "Failed to get DesiredCapacity for AutoScalingGroup ${ECS_CLUSTER_NAME}."
fi

echo "ECS Cluster ${ECS_CLUSTER_NAME} has DesiredCapacity ${desired_capacity}"
if [ "${desired_capacity}" = "0" ]; then
    echo "ECS Cluster ${ECS_CLUSTER_NAME} is scaled down."
    exit 0
fi

echo "AutoScalingGroup is scaled up. Checking age."
instance_id=$(aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "${ECS_CLUSTER_NAME}" \
    --query "AutoScalingGroups[*].Instances[0].InstanceId" \
    --output text)
if [ "${instance_id}" = "" ]; then
    fail "Failed to get InstanceId for AutoScalingGroup ${ECS_CLUSTER_NAME}."
fi

echo "AutoScalingGroup has EC2 Instance ${instance_id}"
launchtime=$(aws ec2 describe-instances \
    --instance-id "${instance_id}" \
    --query "Reservations[0].Instances[0].LaunchTime" \
    --output text)
if [ "${launchtime}" = "" ]; then
    fail "Failed to get LaunchTime for Instance ${instance_id} for AutoScalingGroup ${ECS_CLUSTER_NAME}."
fi

launchtime_unixtime=$(date -d "${launchtime}" -u +%s)
if [ "$?" -ne "0" ]; then
    fail "Failed to convert LaunchTime ${launchtime} for Instance ${instance_id} for AutoScalingGroup ${ECS_CLUSTER_NAME}."
fi

echo "Instance ${instance_id} started at ${launchtime} (${launchtime_unixtime})."

thirtyminutesago_unixtime=$(date -d -30minutes -u +%s)
if [ "${launchtime_unixtime}" -gt "${thirtyminutesago_unixtime}" ]; then
    echo "AutoScalingGroup ${ECS_CLUSTER_NAME} Instance ${instance_id} is up for less than 30 minutes."
    exit 0
fi

message="AutoScalingGroup ${ECS_CLUSTER_NAME} Instance ${instance_id} is up for more than 30 minutes; scaling down."
echo "${message}"

aws autoscaling update-auto-scaling-group \
    --auto-scaling-group-name="${ECS_CLUSTER_NAME}" \
    --min-size 0 --max-size 0 --desired-capacity 0
alert_slack "${message}"
