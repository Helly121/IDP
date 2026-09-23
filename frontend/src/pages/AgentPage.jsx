/**
 * AgentPage - Live AI DevOps mentor full-page chat interface.
 * Connects to POST /api/v1/agent/run and renders multi-step reasoning.
 */

import { useState, useRef, useEffect } from 'react';
import api from '../api/client';
import './AgentPage.css';

const EVENT_ICONS = {
  thinking: '??',
  tool_call: '??',
  tool_result: '??',
  approval_required: '?',
  final_response: '?',
  error: '?',
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
            {expanded ? 'Hide params  ' : 'Show params  '}
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
            {data.tool_name} - {data.success ? 'Success' : 'Failed'}
          </span>
          <button className="btn-expand" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Hide result  ' : 'Show result  '}
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

export default function AgentPage() {
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
    'Provision a new Redis cache for the student-portal project',
    'What pods are running in the default namespace?',
    'Check ArgoCD sync status for idp-backend',
    'Estimate cost for 3 replicas with postgres DB',
  ];

  return (
    <div className="agent-page-container fade-in">
      <div className="agent-page-header">
        <div className="agent-page-title">
          <div className="agent-page-avatar"><svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
            <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#ffffff" />
            <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
          </svg></div>
          <div>
            <h2>DevOps AI Agent</h2>
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

      <div className="agent-page-messages">
        {events.length === 0 && chatHistory.length === 0 && (
          <div className="agent-empty-state">
            <div className="agent-empty-icon"><svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
            <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#ffffff" />
            <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
          </svg></div>
            <h3>DevSecOps AI Mentor</h3>
            <p>I am your AI agent that can provision infrastructure, write and commit GitHub action pipelines, and debug deployments. How can I help you today?</p>
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
              <span className="agent-msg-icon">??</span>
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

      <form className="agent-page-input" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message the DevOps AI agent..."
          disabled={isStreaming}
        />
        <button type="submit" disabled={isStreaming || !input.trim()}>
          {isStreaming ? (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{animation: "pulse-dot 1.2s infinite"}}><circle cx="12" cy="12" r="10"></circle><path d="M12 2a10 10 0 0 1 10 10"></path></svg>) : (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>)}
        </button>
      </form>
    </div>
  );
}
