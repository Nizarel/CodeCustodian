// Container Apps Environment + CodeCustodian Container App
param envName string
param appName string
param location string
param lawCustomerId string

@secure()
param lawSharedKey string

param subnetId string
param acrLoginServer string
param managedIdentityId string
param managedIdentityClientId string
param imageTag string = 'latest'
param appInsightsConnectionString string = ''
param kvUri string = ''
param teamsWebhookUrl string = ''
param useKeyVaultSecret bool = false
param useGithubTokenSecret bool = false

var teamsWebhookSecretUrl = '${kvUri}secrets/TEAMS-WEBHOOK-URL'
var githubTokenSecretUrl = '${kvUri}secrets/github-token'
var teamsWebhookEnv = useKeyVaultSecret
  ? [
      {
        name: 'TEAMS_WEBHOOK_URL'
        secretRef: 'teams-webhook-url'
      }
    ]
  : [
      {
        name: 'TEAMS_WEBHOOK_URL'
        value: teamsWebhookUrl
      }
    ]

// ── Container Apps Environment ────────────────────────────────────────────

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: lawCustomerId
        sharedKey: lawSharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: subnetId
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ── Container App ─────────────────────────────────────────────────────────

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      secrets: concat(
        useKeyVaultSecret
          ? [
              {
                name: 'teams-webhook-url'
                keyVaultUrl: teamsWebhookSecretUrl
                identity: managedIdentityId
              }
            ]
          : [],
        useGithubTokenSecret
          ? [
              {
                name: 'github-token'
                keyVaultUrl: githubTokenSecretUrl
                identity: managedIdentityId
              }
            ]
          : []
      )
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'codecustodian'
          image: '${acrLoginServer}/codecustodian:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(
            [
              {
                name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                value: appInsightsConnectionString
              }
              {
                name: 'AZURE_KEYVAULT_URI'
                value: kvUri
              }
              {
                name: 'AZURE_CLIENT_ID'
                value: managedIdentityClientId
              }
            ],
            teamsWebhookEnv,
            [
              {
                name: 'CHATOPS_ENABLED'
                value: 'true'
              }
            ],
            useGithubTokenSecret
              ? [
                  {
                    name: 'GITHUB_TOKEN'
                    secretRef: 'github-token'
                  }
                ]
              : []
          )
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 10
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output appId string = containerApp.id
