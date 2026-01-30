import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = 'http://localhost:5001/api';

interface Agent {
  name: string;
  title: string;
  description: string;
  enabled: boolean;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  agent?: string;
}

interface Example {
  title: string;
  query: string;
  agent: string | null;
}

function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [examples, setExamples] = useState<Example[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    fetchAgents();
    fetchExamples();
    fetchStatus();
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await axios.get(`${API_URL}/agents`);
      setAgents(response.data.agents);
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const fetchExamples = async () => {
    try {
      const response = await axios.get(`${API_URL}/examples`);
      setExamples(response.data.examples);
    } catch (error) {
      console.error('Error fetching examples:', error);
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/health`);
      setStatus(response.data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: input
    };

    setMessages([...messages, userMessage]);
    const userInput = input;
    setInput('');
    setLoading(true);

    // Add a thinking message
    const thinkingMessage: Message = {
      role: 'assistant',
      content: '🤔 Initializing agent and planning approach...',
      agent: selectedAgent || 'orchestrator'
    };
    setMessages(prev => [...prev, thinkingMessage]);

    try {
      // Try streaming endpoint first
      const streamUrl = `${API_URL}/chat/stream?message=${encodeURIComponent(userInput)}&agent=${encodeURIComponent(selectedAgent || '')}`;
      const eventSource = new EventSource(streamUrl);

      let finalResponse = '';
      let agentUsed = selectedAgent || 'orchestrator';

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'status') {
          // Update thinking message with status
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: `💭 ${data.message}`,
              agent: agentUsed
            };
            return newMessages;
          });
        } else if (data.type === 'response') {
          finalResponse = data.response;
          agentUsed = data.agent_used;
          eventSource.close();
          
          // Replace thinking message with final response
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: finalResponse,
              agent: agentUsed
            };
            return newMessages;
          });
          setLoading(false);
        } else if (data.type === 'error') {
          eventSource.close();
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: `Error: ${data.error}`
            };
            return newMessages;
          });
          setLoading(false);
        }
      };

      eventSource.onerror = async (error) => {
        console.log('Streaming failed, falling back to regular POST');
        eventSource.close();
        
        // Fallback to regular POST request
        try {
          const response = await axios.post(`${API_URL}/chat`, {
            message: userInput,
            agent: selectedAgent
          });

          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: response.data.response,
              agent: response.data.agent_used
            };
            return newMessages;
          });
        } catch (postError: any) {
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: `Error: ${postError.response?.data?.error || postError.message}`
            };
            return newMessages;
          });
        } finally {
          setLoading(false);
        }
      };

    } catch (error: any) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${error.response?.data?.error || error.message}`
      };
      setMessages(prev => [...prev, errorMessage]);
      setLoading(false);
    }
  };

  const loadExample = (example: Example) => {
    setInput(example.query);
    setSelectedAgent(example.agent);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 Business Plan Creator</h1>
        <p>AI-Powered Deep Agents System</p>
        {status && (
          <div className="status">
            <span>Azure OpenAI: {status.deployment}</span>
            <span className="status-dot">●</span>
          </div>
        )}
      </header>

      <div className="main-container">
        <aside className="sidebar">
          <section className="agents-section">
            <h3>Available Agents</h3>
            <div className="agent-selector">
              <button
                className={selectedAgent === null ? 'active' : ''}
                onClick={() => setSelectedAgent(null)}
              >
                🎯 Orchestrator (Auto)
              </button>
              {agents.map(agent => (
                <button
                  key={agent.name}
                  className={selectedAgent === agent.name ? 'active' : ''}
                  onClick={() => setSelectedAgent(agent.name)}
                >
                  {agent.title}
                </button>
              ))}
            </div>
          </section>

          <section className="examples-section">
            <h3>Example Queries</h3>
            {examples.map((example, idx) => (
              <div
                key={idx}
                className="example-card"
                onClick={() => loadExample(example)}
              >
                <strong>{example.title}</strong>
                <p>{example.query.substring(0, 80)}...</p>
              </div>
            ))}
          </section>
        </aside>

        <main className="chat-container">
          <div className="messages">
            {messages.length === 0 && (
              <div className="welcome-message">
                <h2>Welcome to Business Plan Creator</h2>
                <p>Ask questions about competitive analysis, financial metrics, or business planning.</p>
                <p>Try an example query from the sidebar or type your own question below.</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-header">
                  <strong>{msg.role === 'user' ? 'You' : 'AI Assistant'}</strong>
                  {msg.agent && <span className="agent-badge">{msg.agent}</span>}
                </div>
                <div className={`message-content ${msg.content.startsWith('💭') || msg.content.startsWith('🤔') ? 'thinking' : ''}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="message-header">
                  <strong>AI Assistant</strong>
                </div>
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="input-container">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !loading && handleSend()}
              placeholder="Ask about competitive analysis, CoCA calculations, or business planning..."
              disabled={loading}
            />
            <button onClick={handleSend} disabled={loading || !input.trim()}>
              Send
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
