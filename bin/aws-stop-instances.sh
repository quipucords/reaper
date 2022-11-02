#!/usr/bin/env sh
# Immediately stop all running EC2 instances that aren't tagged for bypass.

REAP_BYPASS_TAG="${REAP_BYPASS_TAG:-do-not-delete}"

for region in $(aws ec2 describe-regions \
    --query "Regions[*].RegionName" --output text); do
    echo "Checking $region for running instances"
    for instanceid in $(aws ec2 describe-instances \
        --filters "Name=instance-state-code,Values=16" \
        --query "Reservations[*].Instances[?!not_null(Tags[?Key=='${REAP_BYPASS_TAG}'].Value)].InstanceId" \
        --output text --region "$region"); do
        echo "Stopping '$instanceid' in '$region'"
        aws ec2 stop-instances --instance-ids "$instanceid" --region "$region"
    done
done
