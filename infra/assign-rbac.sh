#!/bin/bash

# This script is run by azd after deployment to assign RBAC roles
# It gets the current user's principal ID and assigns the OpenAI User role

echo "Configuring RBAC role assignments..."

# Get the current user's object ID
PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)

if [ -z "$PRINCIPAL_ID" ]; then
    echo "Error: Could not get current user's principal ID. Make sure you're logged in with 'az login'"
    exit 1
fi

echo "Current user principal ID: $PRINCIPAL_ID"

# Get the OpenAI resource name from azd environment
OPENAI_NAME=$(azd env get-value AZURE_OPENAI_RESOURCE_NAME)

if [ -z "$OPENAI_NAME" ]; then
    echo "Error: Could not get OpenAI resource name from environment"
    exit 1
fi

echo "OpenAI resource name: $OPENAI_NAME"

# Get resource group name
RESOURCE_GROUP=$(azd env get-value AZURE_RESOURCE_GROUP)

if [ -z "$RESOURCE_GROUP" ]; then
    echo "Error: Could not get resource group name from environment"
    exit 1
fi

echo "Resource group: $RESOURCE_GROUP"

# Assign Cognitive Services OpenAI User role
echo "Assigning 'Cognitive Services OpenAI User' role to current user..."

az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role "Cognitive Services OpenAI User" \
    --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$OPENAI_NAME" \
    --output none

if [ $? -eq 0 ]; then
    echo "✓ RBAC role assignment completed successfully"
    echo ""
    echo "Note: It may take up to 5 minutes for the role assignment to propagate."
    echo "If you encounter authentication errors, please wait a few minutes and try again."
else
    echo "✗ Failed to assign RBAC role"
    exit 1
fi
