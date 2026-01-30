#!/usr/bin/env python3
"""
Business Plan Creator - Deep Agents with Dynamic Agent Loading

This script implements a Deep Agents system that dynamically loads specialized 
subagents from markdown specification files in the /agents directory.

Features:
- Dynamic agent loading from markdown files
- YAML frontmatter for agent configuration
- Automatic agent discovery and initialization
- No hardcoded agent definitions
"""

import os
import sys
import time
import yaml
from pathlib import Path
from typing import Literal, Dict, List, Any
from datetime import datetime

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from duckduckgo_search import DDGS
from deepagents import create_deep_agent
from langchain_openai import AzureChatOpenAI

# ============================================================================
# ENVIRONMENT & CONFIGURATION
# ============================================================================

def load_configuration():
    """Load configuration from azd-generated environment file."""
    
    env_path = Path(__file__).parent / ".azure" / "deepagent" / ".env"
    
    if not env_path.exists():
        print(f"Environment file not found at {env_path}")
        print("Please run 'azd up' first to deploy the infrastructure.")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    config = {
        'endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
        'capacity': int(os.getenv('AZURE_OPENAI_CAPACITY', '40')),
        'api_version': '2024-02-15-preview'
    }
    
    if not config['endpoint'] or not config['deployment_name']:
        print("Missing required environment variables")
        print(f"AZURE_OPENAI_ENDPOINT: {config['endpoint']}")
        print(f"AZURE_OPENAI_DEPLOYMENT_NAME: {config['deployment_name']}")
        sys.exit(1)
    
    return config

CONFIG = load_configuration()

# ============================================================================
# AZURE OPENAI AUTHENTICATION SETUP
# ============================================================================

# Set environment variables for LangChain Azure OpenAI integration
os.environ["AZURE_OPENAI_API_VERSION"] = CONFIG['api_version']
os.environ["AZURE_OPENAI_ENDPOINT"] = CONFIG['endpoint']
os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = CONFIG['deployment_name']

# Use DefaultAzureCredential for authentication
credential = DefaultAzureCredential()

# Get token for Azure OpenAI
try:
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    os.environ["AZURE_OPENAI_API_KEY"] = token.token
except Exception as e:
    print(f"Failed to authenticate with Azure: {e}")
    print("Please run 'az login' and ensure RBAC roles are assigned")
    sys.exit(1)

# Create Azure OpenAI model for Deep Agents
model = AzureChatOpenAI(
    azure_deployment=CONFIG['deployment_name'],
    api_version=CONFIG['api_version'],
    azure_endpoint=CONFIG['endpoint'],
    azure_ad_token_provider=lambda: credential.get_token("https://cognitiveservices.azure.com/.default").token
)

# ============================================================================
# DUCKDUCKGO SEARCH WITH PROGRESSIVE BACKOFF
# ============================================================================

def internet_search(
    query: str,
    max_results: int = 5,
    search_type: Literal["general", "news"] = "general"
) -> str:
    """
    Search the internet using DuckDuckGo with progressive backoff (up to 60s).
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        search_type: Type of search ("general" or "news")
        
    Returns:
        Formatted string with search results
    """
    
    max_retries = 5
    initial_backoff = 1.0
    backoff = initial_backoff
    max_backoff = 60.0
    
    for attempt in range(max_retries):
        try:
            with DDGS() as ddgs:
                if search_type == "news":
                    raw_results = list(ddgs.news(query, max_results=max_results))
                else:
                    raw_results = list(ddgs.text(query, max_results=max_results))
            
            if not raw_results:
                return "No results found for this query."
            
            # Format results
            results = []
            for i, r in enumerate(raw_results, 1):
                title = r.get('title', '')
                url = r.get('href', r.get('url', ''))
                snippet = r.get('body', r.get('description', ''))
                
                if title and url:
                    results.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}\n")
            
            if not results:
                return "No valid results found after quality filtering."
            
            return "\n".join(results)
            
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = min(backoff, max_backoff)
                time.sleep(sleep_time)
                backoff *= 2
            else:
                return f"Error: Could not complete search after {max_retries} attempts."
    
    return "Search failed after all retries."

# ============================================================================
# DYNAMIC AGENT LOADING
# ============================================================================

def parse_agent_spec(file_path: Path) -> Dict[str, Any]:
    """
    Parse agent specification from markdown file with YAML frontmatter.
    
    Args:
        file_path: Path to the agent specification markdown file
        
    Returns:
        Dictionary containing agent metadata and system prompt
    """
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split frontmatter and body
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()
        else:
            raise ValueError(f"Invalid frontmatter in {file_path}")
    else:
        raise ValueError(f"No frontmatter found in {file_path}")
    
    # Extract system prompt from markdown body
    # Remove the "# System Prompt" header if present
    system_prompt = body
    if system_prompt.startswith('# System Prompt'):
        system_prompt = '\n'.join(system_prompt.split('\n')[1:]).strip()
    
    return {
        'name': frontmatter.get('name'),
        'title': frontmatter.get('title'),
        'description': frontmatter.get('description'),
        'enabled': frontmatter.get('enabled', True),
        'system_prompt': system_prompt
    }

def load_agent_specs(agents_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all agent specifications from markdown files in the agents directory.
    
    Args:
        agents_dir: Path to the agents directory
        
    Returns:
        List of agent specification dictionaries
    """
    
    specs = []
    
    if not agents_dir.exists():
        print(f"Agents directory not found: {agents_dir}")
        return specs
    
    for file_path in agents_dir.glob('*.md'):
        try:
            spec = parse_agent_spec(file_path)
            if spec['enabled']:
                specs.append(spec)
                print(f"✓ Loaded agent: {spec['title']} ({spec['name']})")
        except Exception as e:
            print(f"✗ Failed to load {file_path.name}: {e}")
    
    return specs

def create_agent_from_spec(spec: Dict[str, Any]) -> Any:
    """
    Create a Deep Agent from an agent specification.
    
    Args:
        spec: Agent specification dictionary
        
    Returns:
        Configured Deep Agent instance
    """
    
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=spec['system_prompt'],
        model=model
    )
    
    return agent

def get_available_agents() -> Dict[str, Any]:
    """
    Get all enabled agents as a dictionary.
    
    Returns:
        Dictionary mapping agent names to agent instances
    """
    
    agents_dir = Path(__file__).parent / "agents"
    specs = load_agent_specs(agents_dir)
    
    agents = {}
    for spec in specs:
        try:
            agent = create_agent_from_spec(spec)
            agents[spec['name']] = {
                'agent': agent,
                'title': spec['title'],
                'description': spec['description']
            }
        except Exception as e:
            print(f"✗ Failed to create agent {spec['name']}: {e}")
    
    return agents

# ============================================================================
# MAIN ORCHESTRATOR AGENT
# ============================================================================

def create_main_orchestrator():
    """
    Create the main Deep Agent orchestrator.
    
    This agent analyzes incoming tasks and uses available tools to complete them.
    """
    
    # Get list of available agents for the system prompt
    agents_dir = Path(__file__).parent / "agents"
    specs = load_agent_specs(agents_dir)
    
    agent_descriptions = "\n".join([
        f"- **{spec['title']}**: {spec['description']}"
        for spec in specs
    ])
    
    system_prompt = f"""You are an Expert Business Planning Orchestrator AI assistant that helps with business planning, research, and analysis.

You are working on a business planning project focused on customer acquisition and competitive strategy.

**Available Specialized Capabilities:**
{agent_descriptions}

**Your Capabilities:**
- Internet search for general research
- Task planning and decomposition (automatically use write_todos)
- File management for context (write_file, read_file)
- Deep research and analysis capabilities

**Guidelines:**
1. Break down complex tasks into manageable steps
2. Use internet_search extensively to gather current, relevant information
3. Store large amounts of information in files to manage context
4. Provide comprehensive, actionable insights
5. Support all recommendations with data and research

Focus on providing high-quality business planning assistance with well-researched, data-driven insights."""

    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=system_prompt,
        model=model
    )
    
    return agent

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def run_example_competitive_analysis():
    """Example: Competitive analysis task."""
    
    print("=" * 70)
    print("EXAMPLE 1: Competitive Analysis")
    print("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Analyze the competitive landscape for project management software tools.
    Focus on the top 3-5 competitors, their pricing models, key features, and market positioning.
    Identify gaps in the market that a new entrant could exploit."""
    
    print(f"\nQuery: {query}\n")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    print(f"\n{'=' * 70}")
    print("RESULT:")
    print(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

def run_example_financial_analysis():
    """Example: Financial analysis task."""
    
    print("=" * 70)
    print("EXAMPLE 2: Financial Analysis (CoCA Calculation)")
    print("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Calculate the Customer Acquisition Cost (CoCA) for a B2B SaaS startup.
    Consider:
    - Marketing spend: $50,000/month
    - Sales team: 3 people @ $8,000/month each
    - New customers acquired: 20/month
    - Research industry benchmarks for B2B SaaS
    - Provide short-term (monthly), medium-term (quarterly), and long-term (annual) CoCA analysis."""
    
    print(f"\nQuery: {query}\n")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    print(f"\n{'=' * 70}")
    print("RESULT:")
    print(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

def run_example_mixed_analysis():
    """Example: Mixed analysis requiring comprehensive research."""
    
    print("=" * 70)
    print("EXAMPLE 3: Comprehensive Business Plan Analysis")
    print("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Create a business plan section for a new AI-powered business intelligence tool.
    
    Include:
    1. Competitive analysis of existing BI tools (Tableau, Power BI, Looker)
    2. Pricing strategy based on competitor analysis
    3. Customer acquisition cost projections for first year
    4. Market positioning and differentiation strategy
    
    Provide a comprehensive analysis with specific recommendations."""
    
    print(f"\nQuery: {query}\n")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    print(f"\n{'=' * 70}")
    print("RESULT:")
    print(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point - run example scenarios."""
    
    print("=" * 70)
    print("BUSINESS PLAN CREATOR - DEEP AGENTS SYSTEM")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Azure OpenAI: {CONFIG['deployment_name']} @ {CONFIG['capacity']}K TPM")
    print("=" * 70)
    print("\nLoading agents...")
    
    # Load and display available agents
    agents = get_available_agents()
    print(f"\n{len(agents)} agent(s) loaded successfully\n")
    
    print("=" * 70)
    
    try:
        # Run example scenarios demonstrating Deep Agents capabilities
        
        # Example 1: Competitive analysis
        print("\n\n")
        run_example_competitive_analysis()
        
        # Example 2: Financial analysis
        print("\n\n")
        run_example_financial_analysis()
        
        # Example 3: Comprehensive mixed analysis
        print("\n\n")
        run_example_mixed_analysis()
        
        print("\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
