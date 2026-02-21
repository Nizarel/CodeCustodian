// ────────────────────────────────────────────────────────────
// CodeCustodian — Azure Infrastructure (main orchestrator)
// Target subscription: da9dea7f-1fc8-44de-93da-ce5c58314cdb
// ────────────────────────────────────────────────────────────

targetScope = 'resourceGroup'

@description('Environment name (dev | staging | prod)')
param environment string = 'prod'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Project name used as a prefix for resource names')
param projectName string = 'codecustodian'

@description('Container image tag')
param imageTag string = 'latest'



// ── Derived names ─────────────────────────────────────────────────────────

var baseName = '${projectName}-${environment}'
var acrName = replace('${projectName}${environment}acr', '-', '')
var kvName = '${baseName}-kv'
var lawName = '${baseName}-law'
var appInsightsName = '${baseName}-ai'
var containerAppEnvName = '${baseName}-env'
var containerAppName = '${baseName}-app'
var vnetName = '${baseName}-vnet'
var managedIdName = '${baseName}-id'

// ── Managed Identity ──────────────────────────────────────────────────────

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    name: managedIdName
    location: location
  }
}

// ── Virtual Network ───────────────────────────────────────────────────────

module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    vnetName: vnetName
    location: location
  }
}

// ── Log Analytics + Application Insights ──────────────────────────────────

module monitor 'modules/monitor.bicep' = {
  name: 'monitor'
  params: {
    lawName: lawName
    appInsightsName: appInsightsName
    location: location
  }
}

// ── Dashboard + Alerts ───────────────────────────────────────────────────

module dashboard 'modules/dashboard.bicep' = {
  name: 'dashboard'
  params: {
    projectName: projectName
    environment: environment
    location: location
    appInsightsId: monitor.outputs.appInsightsId
    lawId: monitor.outputs.lawId
  }
}

module alerts 'modules/alerts.bicep' = {
  name: 'alerts'
  params: {
    projectName: projectName
    environment: environment
    location: location
    appInsightsId: monitor.outputs.appInsightsId
  }
}

// ── Azure Container Registry ──────────────────────────────────────────────

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    acrName: acrName
    location: location
    principalId: identity.outputs.principalId
  }
}

// ── Azure Key Vault ───────────────────────────────────────────────────────

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    kvName: kvName
    location: location
    principalId: identity.outputs.principalId
    tenantId: tenant().tenantId
  }
}

// ── Container Apps Environment + App ──────────────────────────────────────

module containerApp 'modules/container-app.bicep' = {
  name: 'containerApp'
  params: {
    envName: containerAppEnvName
    appName: containerAppName
    location: location
    lawCustomerId: monitor.outputs.lawCustomerId
    lawSharedKey: monitor.outputs.lawSharedKey
    subnetId: network.outputs.containerAppSubnetId
    acrLoginServer: acr.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    imageTag: imageTag
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    kvUri: keyvault.outputs.vaultUri
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────

output acrLoginServer string = acr.outputs.loginServer
output containerAppFqdn string = containerApp.outputs.fqdn
output keyVaultUri string = keyvault.outputs.vaultUri
output appInsightsConnectionString string = monitor.outputs.appInsightsConnectionString
output managedIdentityClientId string = identity.outputs.clientId
output dashboardId string = dashboard.outputs.dashboardId
output alertRuleIds array = alerts.outputs.alertRuleIds
