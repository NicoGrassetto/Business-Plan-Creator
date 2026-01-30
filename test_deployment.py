#!/usr/bin/env python3
"""
Test script to validate Azure OpenAI deployment and authentication.
This script verifies that the infrastructure is correctly deployed and accessible.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

def main():
    """Test Azure OpenAI deployment and authentication."""
    
    print("=" * 60)
    print("Azure OpenAI Deployment Validation")
    print("=" * 60)
    
    # Load environment variables from azd-generated .env file
    env_path = Path(__file__).parent / ".azure" / "deepagent" / ".env"
    
    if not env_path.exists():
        print(f"\n❌ Error: Environment file not found at {env_path}")
        print("\nPlease run 'azd up' first to deploy the infrastructure.")
        sys.exit(1)
    
    load_dotenv(env_path)
    print(f"\n✓ Loaded environment from: {env_path}")
    
    # Get configuration from environment
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    capacity = os.getenv("AZURE_OPENAI_CAPACITY")
    
    if not endpoint or not deployment_name:
        print("\n❌ Error: Missing required environment variables")
        print(f"   AZURE_OPENAI_ENDPOINT: {endpoint}")
        print(f"   AZURE_OPENAI_DEPLOYMENT_NAME: {deployment_name}")
        sys.exit(1)
    
    print(f"\n✓ Configuration loaded:")
    print(f"   Endpoint: {endpoint}")
    print(f"   Deployment: {deployment_name}")
    print(f"   Capacity: {capacity}K TPM")
    
    # Test authentication with DefaultAzureCredential
    print("\n" + "-" * 60)
    print("Testing Authentication...")
    print("-" * 60)
    
    try:
        credential = DefaultAzureCredential()
        print("✓ DefaultAzureCredential initialized")
        
        # Get token provider for Azure OpenAI
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default"
        )
        print("✓ Token provider created")
        
    except Exception as e:
        print(f"\n❌ Authentication Error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Run 'az login' to authenticate")
        print("2. Verify RBAC role assignment (may take up to 5 minutes)")
        print("3. Run: infra/assign-rbac.sh")
        sys.exit(1)
    
    # Create Azure OpenAI client
    print("\n" + "-" * 60)
    print("Testing Azure OpenAI Connection...")
    print("-" * 60)
    
    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_version="2024-02-15-preview",
            azure_ad_token_provider=token_provider
        )
        print("✓ Azure OpenAI client created")
        
    except Exception as e:
        print(f"\n❌ Client Creation Error: {e}")
        sys.exit(1)
    
    # Test a simple completion
    print("\n" + "-" * 60)
    print("Testing Model Completion...")
    print("-" * 60)
    
    try:
        print(f"\nSending test request to {deployment_name}...")
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello! The deployment is working correctly.' in exactly those words."}
            ],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content
        print(f"\n✓ Model Response: {result}")
        
        # Check token usage
        if hasattr(response, 'usage'):
            print(f"\n✓ Token Usage:")
            print(f"   Prompt: {response.usage.prompt_tokens}")
            print(f"   Completion: {response.usage.completion_tokens}")
            print(f"   Total: {response.usage.total_tokens}")
        
    except Exception as e:
        print(f"\n❌ API Call Error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Wait 5 minutes for RBAC propagation")
        print("2. Verify deployment exists in Azure Portal")
        print("3. Check quota limits in your region")
        sys.exit(1)
    
    # All tests passed
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
    print("\nYour Azure OpenAI deployment is ready to use!")
    print("You can now run 'python script.py' to test the Deep Agents.\n")

if __name__ == "__main__":
    main()
