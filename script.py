#!/usr/bin/env python3
"""
Business Plan Creator - Deep Agents with Azure OpenAI GPT-4o

This script implements a Deep Agents system with two specialized subagents:
1. Competitive Analysis Agent - Research market competitors and positioning  
2. Financial Analysis Agent - Calculate CoCA and analyze business metrics

The main orchestrator agent automatically delegates tasks to specialized subagents
based on the nature of the request.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Literal
from datetime import datetime

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from duckduckgo_search import DDGS
from deepagents import create_deep_agent
from langchain_openai import AzureChatOpenAI

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('deep_agents.log')
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# ENVIRONMENT & CONFIGURATION
# ============================================================================

def load_configuration():
    """Load configuration from azd-generated environment file."""
    
    env_path = Path(__file__).parent / ".azure" / "deepagent" / ".env"
    
    if not env_path.exists():
        logger.error(f"Environment file not found at {env_path}")
        logger.info("Please run 'azd up' first to deploy the infrastructure.")
        sys.exit(1)
    
    load_dotenv(env_path)
    logger.info(f"Loaded environment from: {env_path}")
    
    config = {
        'endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
        'capacity': int(os.getenv('AZURE_OPENAI_CAPACITY', '40')),
        'api_version': '2024-02-15-preview'
    }
    
    if not config['endpoint'] or not config['deployment_name']:
        logger.error("Missing required environment variables")
        logger.error(f"AZURE_OPENAI_ENDPOINT: {config['endpoint']}")
        logger.error(f"AZURE_OPENAI_DEPLOYMENT_NAME: {config['deployment_name']}")
        sys.exit(1)
    
    logger.info(f"Configuration loaded: {config['deployment_name']} @ {config['capacity']}K TPM")
    return config

CONFIG = load_configuration()

# ============================================================================
# AZURE OPENAI AUTHENTICATION SETUP
# ============================================================================

# Set environment variables for LangChain Azure OpenAI integration
os.environ["AZURE_OPENAI_API_VERSION"] = CONFIG['api_version']
os.environ["AZURE_OPENAI_ENDPOINT"] = CONFIG['endpoint']
os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = CONFIG['deployment_name']

# Use DefaultAzureCredential for authentication (works with az login locally and Managed Identity in Azure)
credential = DefaultAzureCredential()

# Get token for Azure OpenAI
try:
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    os.environ["AZURE_OPENAI_API_KEY"] = token.token
    logger.info("Azure OpenAI authentication configured successfully")
except Exception as e:
    logger.error(f"Failed to authenticate with Azure: {e}")
    logger.info("Please run 'az login' and ensure RBAC roles are assigned")
    sys.exit(1)

# Create Azure OpenAI model for Deep Agents
model = AzureChatOpenAI(
    azure_deployment=CONFIG['deployment_name'],
    api_version=CONFIG['api_version'],
    azure_endpoint=CONFIG['endpoint'],
    azure_ad_token_provider=lambda: credential.get_token("https://cognitiveservices.azure.com/.default").token
)
logger.info(f"Azure OpenAI model configured: {CONFIG['deployment_name']}")

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
    
    logger.info(f"Internet search: '{query}' (type: {search_type}, max_results: {max_results})")
    
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
                logger.warning(f"No results found for query: '{query}'")
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
                logger.warning(f"No valid results after quality check for: '{query}'")
                return "No valid results found after quality filtering."
            
            logger.info(f"Successfully retrieved {len(results)} results")
            return "\n".join(results)
            
        except Exception as e:
            logger.warning(f"Search attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if attempt < max_retries - 1:
                sleep_time = min(backoff, max_backoff)
                logger.info(f"Retrying in {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                backoff *= 2
            else:
                logger.error(f"All retry attempts exhausted for query: '{query}'")
                return f"Error: Could not complete search after {max_retries} attempts."
    
    return "Search failed after all retries."

# ============================================================================
# SUBAGENT #1: COMPETITIVE ANALYSIS AGENT
# ============================================================================

def create_competitive_analysis_agent():
    """
    Create a specialized subagent for competitive analysis and market research.
    """
    
    system_prompt = """You are a Competitive Analysis Expert specializing in market research and competitive intelligence.

Your expertise includes:
- Identifying and analyzing market competitors
- Evaluating competitive positioning and differentiation
- Comparing product features, pricing, and value propositions
- Analyzing market trends and opportunities
- Identifying competitive advantages and vulnerabilities
- Assessing market share and growth potential

When conducting competitive analysis:
1. Use internet_search to gather information about competitors
2. Analyze pricing strategies, features, and market positioning
3. Identify gaps in the market and potential opportunities
4. Provide actionable insights for competitive strategy
5. Support findings with specific data and examples

You have access to internet search for gathering competitive intelligence.
Focus on providing thorough, data-driven competitive analysis that informs strategic decision-making."""

    logger.info("Creating Competitive Analysis subagent")
    
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=system_prompt,
        model=model
    )
    
    logger.info("Competitive Analysis subagent created")
    return agent

# ============================================================================
# SUBAGENT #2: FINANCIAL ANALYSIS AGENT
# ============================================================================

def create_financial_analysis_agent():
    """
    Create a specialized subagent for financial analysis and CoCA calculations.
    """
    
    system_prompt = """You are a Financial Analysis Expert specializing in business metrics and customer acquisition economics.

Your expertise includes:
- Calculating Customer Acquisition Cost (CoCA) across different timeframes (short, medium, long-term)
- Analyzing sales process economics and conversion funnels
- Researching industry financial benchmarks and metrics
- Evaluating pricing strategies and revenue models
- Assessing unit economics (LTV/CAC ratios, payback periods)
- Providing financial forecasting and scenario analysis

When conducting financial analysis:
1. Use internet_search to gather industry benchmarks and financial data
2. Calculate CoCA considering marketing spend, sales costs, and time horizons
3. Analyze the relationship between sales processes and acquisition costs
4. Provide realistic calculations with adjustable assumptions
5. Consider both direct and indirect costs in your analysis
6. Support recommendations with data and industry comparisons

You have access to internet search for gathering financial benchmarks and data.
Focus on providing accurate, actionable financial analysis that supports business planning and decision-making."""

    logger.info("Creating Financial Analysis subagent")
    
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=system_prompt,
        model=model
    )
    
    logger.info("Financial Analysis subagent created")
    return agent

# ============================================================================
# MAIN ORCHESTRATOR AGENT
# ============================================================================

def create_main_orchestrator():
    """
    Create the main Deep Agent orchestrator with automatic subagent delegation.
    """
    
    system_prompt = """You are an Expert Business Planning Orchestrator AI assistant that helps with business planning, research, and analysis.

You are working on a business planning project focused on customer acquisition and competitive strategy.

When you receive requests:
- For competitive analysis, market research, or competitor information → Conduct thorough competitive analysis
- For financial calculations, CoCA, or pricing analysis → Conduct thorough financial analysis  
- For general business planning questions → Use your internet search capabilities directly

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

    logger.info("Creating Main Orchestrator agent")
    
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=system_prompt,
        model=model
    )
    
    logger.info("Main Orchestrator agent created")
    return agent

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def run_example_competitive_analysis():
    """Example: Competitive analysis task."""
    
    logger.info("=" * 70)
    logger.info("EXAMPLE 1: Competitive Analysis")
    logger.info("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Analyze the competitive landscape for project management software tools.
    Focus on the top 3-5 competitors, their pricing models, key features, and market positioning.
    Identify gaps in the market that a new entrant could exploit."""
    
    logger.info(f"User Query: {query}")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    logger.info(f"\n{'=' * 70}")
    logger.info("RESULT:")
    logger.info(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

def run_example_financial_analysis():
    """Example: Financial analysis task."""
    
    logger.info("=" * 70)
    logger.info("EXAMPLE 2: Financial Analysis (CoCA Calculation)")
    logger.info("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Calculate the Customer Acquisition Cost (CoCA) for a B2B SaaS startup.
    Consider:
    - Marketing spend: $50,000/month
    - Sales team: 3 people @ $8,000/month each
    - New customers acquired: 20/month
    - Research industry benchmarks for B2B SaaS
    - Provide short-term (monthly), medium-term (quarterly), and long-term (annual) CoCA analysis."""
    
    logger.info(f"User Query: {query}")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    logger.info(f"\n{'=' * 70}")
    logger.info("RESULT:")
    logger.info(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

def run_example_mixed_analysis():
    """Example: Mixed analysis requiring comprehensive research."""
    
    logger.info("=" * 70)
    logger.info("EXAMPLE 3: Comprehensive Business Plan Analysis")
    logger.info("=" * 70)
    
    agent = create_main_orchestrator()
    
    query = """Create a business plan section for a new AI-powered business intelligence tool.
    
    Include:
    1. Competitive analysis of existing BI tools (Tableau, Power BI, Looker)
    2. Pricing strategy based on competitor analysis
    3. Customer acquisition cost projections for first year
    4. Market positioning and differentiation strategy
    
    Provide a comprehensive analysis with specific recommendations."""
    
    logger.info(f"User Query: {query}")
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    response = result["messages"][-1].content
    logger.info(f"\n{'=' * 70}")
    logger.info("RESULT:")
    logger.info(f"{'=' * 70}")
    print(f"\n{response}\n")
    
    return response

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point - run example scenarios."""
    
    logger.info("=" * 70)
    logger.info("BUSINESS PLAN CREATOR - DEEP AGENTS SYSTEM")
    logger.info("=" * 70)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Azure OpenAI: {CONFIG['deployment_name']} @ {CONFIG['capacity']}K TPM")
    logger.info("=" * 70)
    
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
        
        logger.info("\n" + "=" * 70)
        logger.info("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\nError during execution: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
