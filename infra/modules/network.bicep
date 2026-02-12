// Virtual Network with Container Apps subnet
param vnetName string
param location string

@description('Address space for the VNet')
param addressPrefix string = '10.0.0.0/16'

@description('Container Apps subnet prefix')
param containerAppSubnetPrefix string = '10.0.0.0/23'

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [addressPrefix]
    }
    subnets: [
      {
        name: 'container-apps'
        properties: {
          addressPrefix: containerAppSubnetPrefix
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output containerAppSubnetId string = vnet.properties.subnets[0].id
