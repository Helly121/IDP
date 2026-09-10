/**
 * AgentPanel — Live AI DevOps mentor with SSE streaming.
 *
 * Connects to POST /api/v1/agent/run and renders the multi-step
 * reasoning (thinking, tool calls, results, approvals) in real-time.
 */

import { useState, useRef, useEffect } from 'react';
import api from '../../api/client';
import './AgentPanel.css';

const EVENT_ICONS = {
  thinking: '🧠',
  tool_call: '🔧',
  tool_result: '📊',
  approval_required: '⏳',
  final_response: '✅',
  error: '❌',
};

function AgentMessage({ event }) {
  const { type, data } = event;
  const [expanded, setExpanded] = useState(false);

  if (type === 'thinking') {
    return (
      <div className="agent-msg agent-msg-thinking">
        <span className="agent-msg-icon">{EVENT_ICONS.thinking}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Thinking</span>
          <p>{data.message}</p>
          <div className="thinking-dots"><span /><span /><span /></div>
        </div>
      </div>
    );
  }

  if (type === 'tool_call') {
    return (
      <div className={`agent-msg agent-msg-tool-call ${data.is_mutating ? 'mutating' : ''}`}>
        <span className="agent-msg-icon">{EVENT_ICONS.tool_call}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">
            Tool Call {data.is_mutating && <span className="badge-mutating">MUTATING</span>}
          </span>
          <code className="tool-name">{data.tool_name}</code>
          <button className="btn-expand" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Hide params ▲' : 'Show params ▼'}
          </button>
          {expanded && (
            <pre className="tool-params">{JSON.stringify(data.params, null, 2)}</pre>
          )}
        </div>
      </div>
    );
  }

  if (type === 'tool_result') {
    return (
      <div className={`agent-msg agent-msg-tool-result ${data.success ? 'success' : 'failure'}`}>
        <span className="agent-msg-icon">{EVENT_ICONS.tool_result}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">
            {data.tool_name} — {data.success ? 'Success' : 'Failed'}
          </span>
          <button className="btn-expand" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Hide result ▲' : 'Show result ▼'}
          </button>
          {expanded && (
            <pre className="tool-params">{JSON.stringify(data.result, null, 2)}</pre>
          )}
        </div>
      </div>
    );
  }

  if (type === 'approval_required') {
    return (
      <div className="agent-msg agent-msg-approval">
        <span className="agent-msg-icon">{EVENT_ICONS.approval_required}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Approval Required</span>
          <p>{data.message}</p>
          <div className="approval-details">
            <code>{data.tool_name}</code>
            <span className="approval-id">ID: {data.action_id?.slice(0, 8)}...</span>
          </div>
          <p className="approval-hint">A guide or admin must approve this action in the Approvals Dashboard.</p>
        </div>
      </div>
    );
  }

  if (type === 'final_response') {
    return (
      <div className="agent-msg agent-msg-final">
        <span className="agent-msg-icon">{EVENT_ICONS.final_response}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Agent Response</span>
          <div className="agent-response-text">{data.message}</div>
        </div>
      </div>
    );
  }

  if (type === 'error') {
    return (
      <div className="agent-msg agent-msg-error">
        <span className="agent-msg-icon">{EVENT_ICONS.error}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Error</span>
          <p>{data.message}</p>
        </div>
      </div>
    );
  }

  return null;
}

export default function AgentPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [events, setEvents] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');
    setIsStreaming(true);

    // Add user message to history
    setChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);
    setEvents([]);

    try {
      const response = await api.runAgent(userMessage);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEventType = null;

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && currentEventType) {
            try {
              const payload = JSON.parse(line.slice(6));
              setEvents(prev => [...prev, { type: currentEventType, data: payload.data }]);
            } catch {
              // Skip malformed JSON
            }
            currentEventType = null;
          }
        }
      }
    } catch (err) {
      setEvents(prev => [...prev, {
        type: 'error',
        data: { message: `Connection failed: ${err.message}` },
      }]);
    } finally {
      setIsStreaming(false);
    }
  };

  const quickPrompts = [
    'What pods are running in the default namespace?',
    'Analyze CrashLoopBackOff logs for my-service',
    'Check ArgoCD sync status for idp-backend',
    'Estimate cost for 3 replicas with postgres DB',
  ];

  return (
    <>
      {/* Floating trigger button */}
      <button
        className={`agent-fab ${isOpen ? 'open' : ''}`}
        onClick={() => {
          setIsOpen(!isOpen);
          setTimeout(() => inputRef.current?.focus(), 100);
        }}
        title="AI DevOps Mentor"
      >
        {isOpen ? '✕' : '🤖'}
      </button>

      {/* Panel */}
      <div className={`agent-panel ${isOpen ? 'open' : ''}`}>
        <div className="agent-panel-header">
          <div className="agent-panel-title">
            <span className="agent-avatar">🤖</span>
            <div>
              <h3>DevOps AI Agent</h3>
              <span className="agent-status">
                {isStreaming ? (
                  <><span className="status-dot streaming" /> Streaming...</>
                ) : (
                  <><span className="status-dot online" /> Online</>
                )}
              </span>
            </div>
          </div>
        </div>

        <div className="agent-panel-messages">
          {events.length === 0 && chatHistory.length === 0 && (
            <div className="agent-empty-state">
              <div className="agent-empty-icon">🤖</div>
              <h4>AI DevOps Mentor</h4>
              <p>Ask me to provision infrastructure, debug deployments, or manage your GitOps pipeline.</p>
              <div className="quick-prompts">
                {quickPrompts.map((prompt, i) => (
                  <button
                    key={i}
                    className="quick-prompt-btn"
                    onClick={() => {
                      setInput(prompt);
                      inputRef.current?.focus();
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chatHistory.map((msg, i) => (
            msg.role === 'user' && (
              <div key={`user-${i}`} className="agent-msg agent-msg-user">
                <span className="agent-msg-icon">👤</span>
                <div className="agent-msg-body">
                  <span className="agent-msg-label">You</span>
                  <p>{msg.content}</p>
                </div>
              </div>
            )
          ))}

          {events.map((event, i) => (
            <AgentMessage key={i} event={event} />
          ))}

          <div ref={messagesEndRef} />
        </div>

        <form className="agent-panel-input" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the AI agent..."
            disabled={isStreaming}
          />
          <button type="submit" disabled={isStreaming || !input.trim()}>
            {isStreaming ? '⏳' : '➤'}
          </button>
        </form>
      </div>
    </>
  );
}
