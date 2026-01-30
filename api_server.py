"""
Backend API Server for Business Plan Creator

This Flask server provides REST API endpoints for the React frontend
to interact with the Deep Agents system.
"""

import os
import sys
import time
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json

# Import Deep Agents configuration
sys.path.append(str(Path(__file__).parent))
from script import (
    CONFIG, model, internet_search,
    load_agent_specs, create_agent_from_spec,
    create_main_orchestrator
)

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'azure_endpoint': CONFIG['endpoint'],
        'deployment': CONFIG['deployment_name'],
        'capacity': CONFIG['capacity']
    })

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get list of available agents."""
    try:
        agents_dir = Path(__file__).parent / "agents"
        specs = load_agent_specs(agents_dir)
        
        agents = [{
            'name': spec['name'],
            'title': spec['title'],
            'description': spec['description'],
            'enabled': spec['enabled']
        } for spec in specs]
        
        return jsonify({'agents': agents})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Process a chat message with the Deep Agents system.
    
    Request body:
    {
        "message": "Your question here",
        "agent": "optional-agent-name"  // If not provided, uses main orchestrator
    }
    """
    try:
        data = request.json
        message = data.get('message')
        agent_name = data.get('agent')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Log to terminal
        print("\n" + "="*70)
        print(f"📨 Incoming Request")
        print("="*70)
        print(f"User Message: {message[:100]}...")
        print(f"Selected Agent: {agent_name or 'orchestrator (auto)'}")
        print("="*70)
        
        # Create agent (specific or orchestrator)
        if agent_name:
            agents_dir = Path(__file__).parent / "agents"
            specs = load_agent_specs(agents_dir)
            spec = next((s for s in specs if s['name'] == agent_name), None)
            
            if not spec:
                return jsonify({'error': f'Agent {agent_name} not found'}), 404
            
            print(f"🤖 Creating {spec['title']}...")
            agent = create_agent_from_spec(spec)
        else:
            print("🎯 Creating Main Orchestrator...")
            agent = create_main_orchestrator()
        
        print("💭 Agent is thinking...\n")
        
        # Invoke agent
        result = agent.invoke({
            "messages": [{"role": "user", "content": message}]
        })
        
        response = result["messages"][-1].content
        
        print("\n" + "="*70)
        print("✅ Response Generated")
        print("="*70)
        print(f"Length: {len(response)} characters")
        print(f"Preview: {response[:150]}...")
        print("="*70 + "\n")
        
        return jsonify({
            'response': response,
            'agent_used': agent_name or 'orchestrator'
        })
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/stream', methods=['GET'])
def chat_stream():
    """
    Stream chat response with progress updates.
    """
    def generate():
        try:
            message = request.args.get('message')
            agent_name = request.args.get('agent')
            if agent_name == '':
                agent_name = None
            
            if not message:
                yield f"data: {json.dumps({'error': 'Message is required'})}\n\n"
                return
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing agent...'})}\n\n"
            time.sleep(0.1)
            
            # Create agent
            if agent_name:
                agents_dir = Path(__file__).parent / "agents"
                specs = load_agent_specs(agents_dir)
                spec = next((s for s in specs if s['name'] == agent_name), None)
                
                if not spec:
                    error_msg = {'error': f'Agent {agent_name} not found'}
                    yield f"data: {json.dumps(error_msg)}\n\n"
                    return
                
                status_msg = {'type': 'status', 'message': f'Creating {spec["title"]}...'}
                yield f"data: {json.dumps(status_msg)}\n\n"
                agent = create_agent_from_spec(spec)
            else:
                status_msg = {'type': 'status', 'message': 'Creating orchestrator...'}
                yield f"data: {json.dumps(status_msg)}\n\n"
                agent = create_main_orchestrator()
            
            status_msg = {'type': 'status', 'message': 'Agent is thinking and planning...'}
            yield f"data: {json.dumps(status_msg)}\n\n"
            
            # Invoke agent
            result = agent.invoke({
                "messages": [{"role": "user", "content": message}]
            })
            
            response = result["messages"][-1].content
            
            # Send final response
            result_msg = {'type': 'response', 'response': response, 'agent_used': agent_name or 'orchestrator'}
            yield f"data: {json.dumps(result_msg)}\n\n"
            
        except Exception as e:
            error_msg = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/examples', methods=['GET'])
def get_examples():
    """Get example queries for each agent type."""
    return jsonify({
        'examples': [
            {
                'title': 'Competitive Analysis',
                'query': 'Analyze the competitive landscape for project management software tools. Focus on the top 3-5 competitors, their pricing models, key features, and market positioning.',
                'agent': 'competitive-analysis'
            },
            {
                'title': 'Financial Analysis (CoCA)',
                'query': 'Calculate the Customer Acquisition Cost (CoCA) for a B2B SaaS startup with marketing spend of $50,000/month, sales team of 3 people @ $8,000/month each, and 20 new customers/month.',
                'agent': 'financial-analysis'
            },
            {
                'title': 'Comprehensive Business Plan',
                'query': 'Create a business plan section for a new AI-powered business intelligence tool including competitive analysis, pricing strategy, and market positioning.',
                'agent': None  # Uses orchestrator
            }
        ]
    })

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("BUSINESS PLAN CREATOR - API SERVER")
    print("=" * 70)
    print(f"Azure OpenAI: {CONFIG['deployment_name']} @ {CONFIG['capacity']}K TPM")
    print(f"API Server: http://localhost:5001")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
