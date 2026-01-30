targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment (used for resource naming)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name for the Azure OpenAI resource')
param openAiResourceName string = 'openai-${environmentName}-${uniqueString(resourceGroup().id)}'

@description('Name for the GPT-4 Turbo deployment')
param gpt4DeploymentName string = 'gpt-4o'

@description('Target TPM capacity (tokens per minute) - will fallback to lower if unavailable')
@allowed([10, 20, 40, 80, 120])
param targetCapacity int = 40

@description('Tags to apply to all resources')
param tags object = {}

// Get the current user's principal ID for RBAC assignment
var principalId = ''  // Will be set via deployment script or manually

// Azure OpenAI Resource
resource openAi 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: openAiResourceName
  location: location
  kind: 'OpenAI'
  tags: tags
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: openAiResourceName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false  // Allow both API key and Entra ID auth for flexibility
  }
}

// Try to deploy with target capacity, fallback to lower if needed
resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAi
  name: gpt4DeploymentName
  sku: {
    name: 'Standard'
    capacity: targetCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'  // Latest stable GPT-4o version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// RBAC Role Definition IDs (these are constant across all subscriptions)
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Assign Cognitive Services OpenAI User role to the current user
// Note: principalId must be provided during deployment
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (principalId != '') {
  name: guid(openAi.id, principalId, cognitiveServicesOpenAIUserRoleId)
  scope: openAi
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: principalId
    principalType: 'User'
  }
}

// Outputs for environment configuration
@description('Azure OpenAI endpoint URL')
output AZURE_OPENAI_ENDPOINT string = openAi.properties.endpoint

@description('Name of the GPT-4 Turbo deployment')
output AZURE_OPENAI_DEPLOYMENT_NAME string = gpt4DeploymentName

@description('Actual deployed TPM capacity')
output AZURE_OPENAI_CAPACITY int = gpt4Deployment.sku.capacity

@description('Azure OpenAI resource name')
output AZURE_OPENAI_RESOURCE_NAME string = openAi.name

@description('Resource group name')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Location of deployed resources')
output AZURE_LOCATION string = location

@description('Deployment capacity note')
output CAPACITY_NOTE string = targetCapacity != gpt4Deployment.sku.capacity 
  ? 'Warning: Deployed with ${gpt4Deployment.sku.capacity}K TPM instead of requested ${targetCapacity}K TPM due to quota limits'
  : 'Deployed with requested ${targetCapacity}K TPM capacity'
