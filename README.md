# Reaper

Purpose of this repo is clean up any running instances in our dev cloud accounts. There are two components, a docker container with awscli in it, and github actions workflow file that actually drives the reaping with previously mentioned container. If you'd like to modify the cleanup behavior, modify the schedule.yml workflow file.

## Development

See [development.md](development.md) for information about running reaper commands in your local development environment.
