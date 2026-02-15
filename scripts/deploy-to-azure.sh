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

echo "==> Setting subscription to $SUBSCRIPTION"
az account set --subscription "$SUBSCRIPTION"

echo "==> Creating resource group $RESOURCE_GROUP in $LOCATION"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags project=codecustodian environment="$ENVIRONMENT"

echo "==> Deploying Bicep template"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters "infra/parameters.${ENVIRONMENT}.bicepparam" \
  --parameters imageTag="$IMAGE_TAG" \
  --name "codecustodian-$(date +%Y%m%d%H%M%S)"

echo "==> Deployment complete"
az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$(az deployment group list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)" \
  --query properties.outputs
