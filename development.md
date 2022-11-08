# Local development

How do I run the reaper commands locally?

Note: The commands in this document use `docker`. They _probably_ also work with `podman` and other standard container managers/engines/runtimes, but your mileage may vary.

## Azure prerequisites

reaper needs credentials for an Azure service principal or user that has permissions to get, list, and shut down VMs.

How do I define this in portal.azure.com? This process is generally described [in this Azure document](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal), but these are the main steps:

1. log in to https://portal.azure.com as an admin/owner.
2. Go to Azure Active Directory: App registrations: New registration.
3. Name it something obvious like `github-reaper-app`.
    - Select "Accounts in this organizational directory only".
    - Skip "Redirect URI".
4. Go to Azure Active Directory: App registrations: `github-reaper-app`
    - Copy the "Application (client) ID" value. Store this for later use as your `AZURE_CLIENT_ID`.
    - Copy the "Directory (tenant) ID" value. Store this for later use as your `AZURE_TENANT_ID`.
5. Go to Azure Active Directory: App registrations: `github-reaper-app`: Certificates & secrets
    - In the "Client secrets" tab, click "+ New client secret".
    - Give it a description like `key for GitHub reaper automation`.
    - Select an appropriate "Expires" value.
    - Click Add.
6. Copy the "Value" value. Store this for later use as your `AZURE_CLIENT_SECRET`.
    - **Important note**: The Value is shown only once. If you do not store it now, you must delete the secret and create a new one.
7. Go to Subscriptions: your subscription name
    - Copy the "Subscription ID" value. Store this for later use as your `AZURE_SUBSCRIPTION_ID`.
8. Go to Subscriptions: your subscription name: Access control (IAM): Add: Add role assignment
    - In the Roles tab, select "Contributor". Click Next.
    - In the Members tab, click "+ Select members", search for your app name, select it, click Select, and click "Review + assign".
    - In the Review + assign tab, click "Review + assign".


## Using Docker

Build the latest local image:

```sh
docker build -t reaper:latest .
```

Create a `.env` file containing appropriate values for:

```sh
AWS_DEFAULT_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AZURE_TENANT_ID=
AZURE_SUBSCRIPTION_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
REAP_AGE_SNAPSHOTS=
REAP_AGE_VOLUMES=
REAP_DRYRUN=
REAP_BYPASS_TAG=
```

reap AWS:

```sh
echo "export AWS_DEFAULT_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
export REAP_AGE_SNAPSHOTS REAP_AGE_VOLUMES REAP_DRYRUN REAP_BYPASS_TAG WEBHOOK_URL
sh ./bin/aws-zero-autoscaling.sh
sh ./bin/aws-stop-instances.sh
poetry run python -m reaper.aws_delete" | \
docker run -i \
    --env-file .env \
    -w /opt/reaper \
    reaper:latest \
    /bin/bash
```

reap Azure:

```sh
echo "export REAP_BYPASS_TAG
export AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET
poetry run python -m reaper.azure_power_off_vms" | \
docker run -i \
    --env-file .env \
    -w /opt/reaper \
    reaper:latest \
    /bin/bash
```

## Using local Poetry virtualenv

```sh
poetry install
```

Read appropriate values into environment variables:

```sh
read -r AZURE_TENANT_ID
read -r AZURE_SUBSCRIPTION_ID
read -r AZURE_CLIENT_ID
read -rs AZURE_CLIENT_SECRET
read -r REAP_BYPASS_TAG  # optionally override the default "do-not-delete"
```

reap Azure:

```sh
AZURE_TENANT_ID="${AZURE_TENANT_ID}" \
AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}" \
AZURE_CLIENT_ID="${AZURE_CLIENT_ID}" \
AZURE_CLIENT_SECRET="${AZURE_CLIENT_SECRET}" \
REAP_BYPASS_TAG="${REAP_BYPASS_TAG}" \
poetry run python3 -m reaper.azure_power_off_vms
```
