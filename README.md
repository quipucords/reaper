# Reaper

Purpose of this repo is clean up any running instances in our dev cloud accounts. There are two components, a docker container with awscli in it, and .gitlab-ci.yml file that actually drives the reaping with previously mentioned container. If you'd like to modify the cleanup behavior, modify the `script` section in the `.Reaper` step.
