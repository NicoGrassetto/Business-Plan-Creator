# Business Plan Creator - Deep Agents System

An intelligent business planning assistant powered by LangChain Deep Agents, Azure OpenAI GPT-4o, and automated task delegation to specialized subagents.

## 🎯 Overview

This project implements a sophisticated AI agent system that helps with business planning tasks by automatically delegating complex analysis to specialized subagents:

- **Main Orchestrator Agent**: Analyzes requests and intelligently delegates to specialized subagents
- **Competitive Analysis Agent**: Market research, competitor analysis, and positioning strategy
- **Financial Analysis Agent**: Customer Acquisition Cost (CoCA) calculations and financial metrics

The system uses:
- **Azure OpenAI GPT-4o** (latest stable model with excellent reasoning)
- **Managed Identity authentication** (no API keys stored locally)
- **DuckDuckGo search** with progressive backoff for internet research
- **Deep Agents framework** with automatic planning and file management
- **Comprehensive logging** for monitoring agent operations

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│         Main Orchestrator Agent                 │
│  (Analyzes tasks, delegates automatically)      │
└─────────┬───────────────────────────┬───────────┘
          │                           │
          ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐
│ Competitive         │    │ Financial           │
│ Analysis Agent      │    │ Analysis Agent      │
│                     │    │                     │
│ • Market research   │    │ • CoCA calculations │
│ • Competitor        │    │ • Financial metrics │
│   analysis          │    │ • Pricing strategy  │
│ • Positioning       │    │ • Benchmarking      │
└─────────────────────┘    └─────────────────────┘
          │                           │
          └──────────┬────────────────┘
                     ▼
            ┌─────────────────┐
            │  DuckDuckGo     │
            │  Search         │
            │  (Rate Limited) │
            └─────────────────┘
```

## 📋 Prerequisites

Before you begin, ensure you have:

- **Azure subscription** with access to Azure OpenAI
- **Azure OpenAI service approval** (apply at [aka.ms/oai/access](https://aka.ms/oai/access))
- **Azure Developer CLI (azd)** installed ([installation guide](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd))
- **Azure CLI** installed ([installation guide](https://learn.microsoft.com/cli/azure/install-azure-cli))
- **Python 3.11 or higher** installed (required for deepagents package)
- **macOS, Linux, or Windows** with bash/zsh

### Install Azure Developer CLI (macOS)

```bash
brew install azure-dev
```

Or use the install script:
```bash
curl -fsSL https://aka.ms/install-azd.sh | bash
```

### Install Azure CLI (macOS)

```bash
brew install azure-cli
```

## 🚀 Quick Start

### 1. Deploy Azure Infrastructure

First, authenticate with Azure and deploy the infrastructure:

```bash
# Login to Azure
az login
azd auth login

# Deploy infrastructure (will prompt for region selection)
azd up
```

During `azd up`, you'll be prompted to:
- Choose an Azure subscription
- Select an Azure region (choose one with GPT-4 Turbo availability)
- Provide an environment name (default: "dev")

The deployment will:
- Create an Azure OpenAI resource
- Deploy GPT-4o model (40K TPM, fallback to 20K/10K if unavailable)
- Assign RBAC role ("Cognitive Services OpenAI User") to your account
- Generate `.azure/deepagent/.env` with configuration

**Note**: RBAC role assignment can take up to 5 minutes to propagate. If you encounter authentication errors, wait a few minutes and try again.

### 2. Assign RBAC Role (if needed)

If you encounter authentication issues, manually run:

```bash
./infra/assign-rbac.sh
```

### 3. Set Up Python Environment

**Important**: Deep Agents requires Python 3.11 or higher.

Create a virtual environment and install dependencies:

```bash
# Create virtual environment with Python 3.11+ (adjust version as needed)
python3.11 -m venv venv
# or
python3.13 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Validate Deployment

Test that everything is working:

```bash
python test_deployment.py
```

You should see:
```
============================================================
Azure OpenAI Deployment Validation
============================================================

✓ Loaded environment from: .azure/deepagent/.env
✓ Configuration loaded:
   Endpoint: https://openai-deepagent-xxxxx.openai.azure.com
   Deployment: gpt-4o
   Capacity: 40K TPM

------------------------------------------------------------
Testing Authentication...
------------------------------------------------------------
✓ DefaultAzureCredential initialized
✓ Token provider created

------------------------------------------------------------
Testing Azure OpenAI Connection...
------------------------------------------------------------
✓ Azure OpenAI client created

------------------------------------------------------------
Testing Model Completion...
------------------------------------------------------------
✓ Model Response: Hello! The deployment is working correctly.
✓ Token Usage:
   Prompt: 25
   Completion: 10
   Total: 35

============================================================
✓ ALL TESTS PASSED
============================================================
```

### 5. Run Deep Agents Examples

Run the example scenarios:

```bash
python script.py
```

This will run three examples demonstrating automatic delegation:
1. **Competitive Analysis**: Market research for project management tools
2. **Financial Analysis**: CoCA calculations for B2B SaaS
3. **Mixed Analysis**: Comprehensive business plan with both agents

## 📊 Cost Estimation

Azure OpenAI GPT-4o pricing (as of January 2026):

| Capacity | Cost (per 1K tokens) | Estimated Monthly Cost* |
|----------|---------------------|-------------------------|
| 10K TPM  | Input: $0.01<br>Output: $0.03 | ~$50-200/month |
| 20K TPM  | Input: $0.01<br>Output: $0.03 | ~$100-400/month |
| 40K TPM  | Input: $0.01<br>Output: $0.03 | ~$200-800/month |

\* Based on moderate usage (100-400 requests/day). Actual costs depend on usage patterns.

### Cost Optimization Tips

1. **Monitor Token Usage**: Check the `deep_agents.log` file for token consumption
2. **Set Budget Alerts**: Configure Azure Cost Management alerts
3. **Use Lower Capacity**: Start with 10K TPM if this is for development/testing
4. **Rate Limiting**: The system automatically rate-limits based on your TPM capacity
5. **Azure Portal Monitoring**: Track usage in Azure Portal → Azure OpenAI → Metrics

### Check Current Usage

```bash
# View deployment details
az cognitiveservices account deployment show \
  --name $(azd env get-value AZURE_OPENAI_RESOURCE_NAME) \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --deployment-name gpt-4o
```

## 🔧 Configuration

### Environment Variables

After running `azd up`, configuration is automatically stored in `.azure/deepagent/.env`:

```bash
AZURE_OPENAI_ENDPOINT=https://openai-deepagent-xxxxx.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_CAPACITY=40
AZURE_OPENAI_RESOURCE_NAME=openai-deepagent-xxxxx
AZURE_RESOURCE_GROUP=rg-deepagent
AZURE_LOCATION=swedencentral
```

### Adjust TPM Capacity

To change the TPM capacity after deployment:

```bash
# Edit infra/main.parameters.json
# Change targetCapacity value (10, 20, 40, 80, or 120)

# Redeploy
azd up
```

### Change Azure Region

```bash
# Set different region
azd env set AZURE_LOCATION westeurope

# Redeploy
azd up
```

## 📖 Usage Examples

### Example 1: Competitive Analysis

```python
from script import create_main_orchestrator

agent = create_main_orchestrator()

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Analyze competitors in the CRM software market"
    }]
})

print(result["messages"][-1].content)
```

### Example 2: Financial Analysis

```python
from script import create_main_orchestrator

agent = create_main_orchestrator()

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": """Calculate CoCA for:
        - Marketing: $30K/month
        - Sales team: 2 people @ $7K/month
        - New customers: 15/month"""
    }]
})

print(result["messages"][-1].content)
```

### Example 3: Custom Query

```python
from script import create_main_orchestrator

agent = create_main_orchestrator()

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Your business planning question here..."
    }]
})

print(result["messages"][-1].content)
```

## 🐛 Troubleshooting

### Authentication Errors

**Error**: `DefaultAzureCredential failed to retrieve a token`

**Solutions**:
1. Run `az login` to authenticate
2. Wait 5 minutes for RBAC propagation
3. Run `./infra/assign-rbac.sh`
4. Verify role assignment:
   ```bash
   az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv) --all
   ```

### Quota Errors

**Error**: `Deployment failed due to insufficient quota`

**Solutions**:
1. Choose a different Azure region with availability
2. Request quota increase in Azure Portal
3. Use lower TPM capacity (20K or 10K)
4. Check regional availability:
   ```bash
   az cognitiveservices account list-models --location eastus --kind OpenAI
   ```

### DuckDuckGo Rate Limiting

**Error**: `Search attempts exhausted`

**Solutions**:
- The system automatically retries with progressive backoff (up to 60s)
- If persistent, reduce search frequency in queries
- Consider alternative search providers (requires code modification)

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'deepagents'`

**Solutions**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## 📁 Project Structure

```
Business-Plan-Creator/
├── .azure/                           # azd generated config
│   └── dev/
│       └── .env                      # Environment variables
├── .azure-dev/
│   └── config.json                   # azd configuration
├── infra/                            # Infrastructure as Code
│   ├── main.bicep                    # Azure OpenAI deployment
│   ├── main.parameters.json          # Deployment parameters
│   └── assign-rbac.sh                # RBAC assignment script
├── venv/                             # Python virtual environment
├── azure.yaml                        # azd project definition
├── requirements.txt                  # Python dependencies
├── script.py                         # Deep Agents implementation
├── test_deployment.py                # Deployment validation
├── deep_agents.log                   # Agent operations log
├── .gitignore                        # Git ignore rules
└── README.md                         # This file
```

## 🔐 Security Notes

- **No API Keys Stored**: Uses Managed Identity + Azure CLI credentials
- **RBAC-Based Access**: Fine-grained access control via Azure RBAC
- **Local Development**: Uses `az login` credentials automatically
- **Production Deployment**: Enable Managed Identity on Azure resources (VMs, App Service, Functions)

## 🧹 Cleanup

To delete all Azure resources and clean up:

```bash
# Delete all Azure resources
azd down --purge

# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv/

# Remove Azure config
rm -rf .azure/
```

## 📚 Additional Resources

- [LangChain Deep Agents Documentation](https://docs.langchain.com/oss/python/deepagents/quickstart)
- [Azure OpenAI Service Documentation](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure Developer CLI Documentation](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Azure Identity SDK](https://learn.microsoft.com/python/api/overview/azure/identity-readme)

## 📝 License

This project is provided as-is for educational and development purposes.

## 🤝 Contributing

Feel free to customize the agents, add new subagents, or enhance the system based on your specific business planning needs!

---

**Built with** ❤️ **using LangChain Deep Agents, Azure OpenAI GPT-4o, and Azure Developer CLI**
