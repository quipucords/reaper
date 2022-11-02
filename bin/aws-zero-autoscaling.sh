#!/usr/bin/env sh
# Immediately shut down ECS clusters by setting autoscaling capacity to 0.

for region in $(aws ec2 describe-regions \
    --query "Regions[*].RegionName" --output text); do
    echo "Checking $region for auto scaling groups"
    for name in $(aws autoscaling describe-auto-scaling-groups \
        --query "AutoScalingGroups[*].AutoScalingGroupName" \
        --output text --region "$region"); do
        echo "Verifying that '$name' in '$region' is scaled down"
        aws autoscaling update-auto-scaling-group \
            --auto-scaling-group-name="$name" \
            --min-size 0 --max-size 0 --desired-capacity 0 \
            --region "$region"
    done
done
