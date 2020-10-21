#!/usr/bin/env sh

if [[ $(aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "${ECS_CLUSTER_NAME}" \
    --query "AutoScalingGroups[*].DesiredCapacity" \
    --output text) -ne 0 ]]; then
    echo "ECS Cluster ${ECS_CLUSTER_NAME} scaled up, checking age."
    export ECS_INSTANCE_ID=$(aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "${ECS_CLUSTER_NAME}" \
        --query "AutoScalingGroups[*].Instances[0].InstanceId" \
        --output text)
    export ECS_INSTANCE_AGE=$(aws ec2 describe-instances \
        --instance-id "${ECS_INSTANCE_ID}" \
        --query "Reservations[0].Instances[0].LaunchTime" \
        --output text)
    echo "ECS Cluster ${ECS_CLUSTER_NAME} started at ${ECS_INSTANCE_AGE}"
    if [[ $(date -d "${ECS_INSTANCE_AGE}" -u +%s) -lt $(date -d -30minutes -u +%s) ]]; then
        echo "ECS Cluster ${ECS_CLUSTER_NAME} up for more than 30 minutes, scaling down."
        aws autoscaling update-auto-scaling-group \
            --auto-scaling-group-name="${ECS_CLUSTER_NAME}" \
            --min-size 0 --max-size 0 --desired-capacity 0 \
            --region ${ECS_REGION}
        curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"ECS Cluster '"${ECS_CLUSTER_NAME}"' up for more than 30 minutes, scaling down instance '"${ECS_INSTANCE_ID}"'."}' \
            ${WEBHOOK_URL}
    else
        echo "ECS Cluster ${ECS_CLUSTER_NAME} up for less than 30 minutes, exiting."
    fi
else
    echo "ECS Cluster ${ECS_CLUSTER_NAME} is scaled down, exiting."
fi
