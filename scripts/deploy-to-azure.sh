#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────
# deploy-to-azure.sh — Deploy CodeCustodian to Azure
# ────────────────────────────────────────────────────────────
set -euo pipefail

SUBSCRIPTION="da9dea7f-1fc8-44de-93da-ce5c58314cdb"
RESOURCE_GROUP="${RESOURCE_GROUP:-Custodian-Rg}"
LOCATION="${LOCATION:-eastus2}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TEAMS_WEBHOOK_URL="${TEAMS_WEBHOOK_URL:-}"
DEPLOYMENT_NAME="codecustodian-$(date +%Y%m%d%H%M%S)"

echo "==> Setting subscription to $SUBSCRIPTION"
az account set --subscription "$SUBSCRIPTION"

echo "==> Creating resource group $RESOURCE_GROUP in $LOCATION"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags project=codecustodian environment="$ENVIRONMENT"

echo "==> Deploying Bicep template"
DEPLOY_ARGS=(
  --resource-group "$RESOURCE_GROUP"
  --template-file infra/main.bicep
  --parameters "infra/parameters.${ENVIRONMENT}.bicepparam"
  --parameters imageTag="$IMAGE_TAG"
  --name "$DEPLOYMENT_NAME"
)

if [ -n "$TEAMS_WEBHOOK_URL" ]; then
  echo "==> Configuring Teams webhook secret via Key Vault"
  DEPLOY_ARGS+=(--parameters teamsWebhookUrl="$TEAMS_WEBHOOK_URL")
else
  echo "==> TEAMS_WEBHOOK_URL not provided; deploying with empty ChatOps webhook secret"
fi

az deployment group create "${DEPLOY_ARGS[@]}"

echo "==> Deployment complete"
az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs

FQDN="$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --query properties.outputs.containerAppFqdn.value \
  -o tsv)"

if [ -z "$FQDN" ]; then
  echo "!! Could not resolve Container App FQDN from deployment outputs"
  exit 1
fi

echo "==> Running health check on https://${FQDN}/health"
curl --retry 5 --retry-delay 10 --retry-all-errors --fail "https://${FQDN}/health"
echo
echo "==> Health check passed"
