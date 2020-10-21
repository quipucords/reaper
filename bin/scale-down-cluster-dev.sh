#!/usr/bin/env sh

for region in $(aws ec2 describe-regions \
    --query "Regions[*].RegionName" --output text); do
    echo "Checking $region"
    for name in $(aws autoscaling describe-auto-scaling-groups \
        --query "AutoScalingGroups[*].AutoScalingGroupName" \
        --output text --region $region); do
        echo "Verifying that '$name' in '$region' is scaled down"
        aws autoscaling update-auto-scaling-group \
            --auto-scaling-group-name="$name" \
            --min-size 0 --max-size 0 --desired-capacity 0 \
            --region $region
    done
    for instanceid in $(aws ec2 describe-instances \
        --filters "Name=instance-state-code,Values=16" \
        --query "Reservations[*].Instances[*].InstanceId" \
        --output text --region $region); do
        echo "Stopping '$instanceid' in '$region'"
        aws ec2 stop-instances --instance-ids $instanceid --region $region
    done
done
