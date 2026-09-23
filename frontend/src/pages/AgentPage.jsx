/**
 * AgentPage - Live AI DevOps mentor full-page chat interface.
 * Connects to POST /api/v1/agent/run and renders multi-step reasoning.
 */

import { useState, useRef, useEffect } from 'react';
import api from '../api/client';
import './AgentPage.css';

// Clean SVG Icons for event types
const EventIcons = {
  thinking: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6ee7b7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: "pulse-dot 1.4s infinite" }}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  ),
  tool_call: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  ),
  tool_result: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6ee7b7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  approval_required: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fb923c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  final_response: (
    <svg width="20" height="20" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="14" stroke="#6ee7b7" strokeWidth="2" />
      <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#6ee7b7" />
      <circle cx="18.5" cy="14.5" r="9.5" fill="#0b0f19" />
    </svg>
  ),
  error: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  ),
  user: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6ee7b7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
};

function AgentMessage({ event }) {
  const { type, data } = event;
  const [expanded, setExpanded] = useState(false);

  if (type === 'thinking') {
    return (
      <div className="agent-msg agent-msg-thinking">
        <span className="agent-msg-icon">{EventIcons.thinking}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Thinking</span>
          <p>{data?.message || 'Analyzing your request and determining the best approach...'}</p>
          <div className="thinking-dots"><span /><span /><span /></div>
        </div>
      </div>
    );
  }

  if (type === 'tool_call') {
    return (
      <div className={`agent-msg agent-msg-tool-call ${data?.is_mutating ? 'mutating' : ''}`}>
        <span className="agent-msg-icon">{EventIcons.tool_call}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">
            Tool Call {data?.is_mutating && <span className="badge-mutating">MUTATING</span>}
          </span>
          <code className="tool-name">{data?.tool_name}</code>
          {data?.params && Object.keys(data.params).length > 0 && (
            <>
              <button className="btn-expand" onClick={() => setExpanded(!expanded)}>
                {expanded ? 'Hide params' : 'Show params'}
              </button>
              {expanded && (
                <pre className="tool-params">{JSON.stringify(data.params, null, 2)}</pre>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  if (type === 'tool_result') {
    return (
      <div className={`agent-msg agent-msg-tool-result ${data?.success ? 'success' : 'failure'}`}>
        <span className="agent-msg-icon">{EventIcons.tool_result}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">
            {data?.tool_name} - {data?.success ? 'Success' : 'Failed'}
          </span>
          {data?.result && (
            <>
              <button className="btn-expand" onClick={() => setExpanded(!expanded)}>
                {expanded ? 'Hide result' : 'Show result'}
              </button>
              {expanded && (
                <pre className="tool-params">{JSON.stringify(data.result, null, 2)}</pre>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  if (type === 'approval_required') {
    return (
      <div className="agent-msg agent-msg-approval">
        <span className="agent-msg-icon">{EventIcons.approval_required}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Approval Required</span>
          <p>{data?.message}</p>
          <div className="approval-details">
            <code>{data?.tool_name}</code>
            <span className="approval-id">ID: {data?.action_id?.slice(0, 8)}...</span>
          </div>
          <p className="approval-hint">A guide or admin must approve this action in the Approvals Dashboard.</p>
        </div>
      </div>
    );
  }

  if (type === 'final_response') {
    return (
      <div className="agent-msg agent-msg-final">
        <span className="agent-msg-icon">{EventIcons.final_response}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">DevOps Mentor</span>
          <div className="agent-response-text">{data?.message}</div>
        </div>
      </div>
    );
  }

  if (type === 'error') {
    return (
      <div className="agent-msg agent-msg-error">
        <span className="agent-msg-icon">{EventIcons.error}</span>
        <div className="agent-msg-body">
          <span className="agent-msg-label">Error</span>
          <p>{data?.message || 'An unexpected error occurred.'}</p>
        </div>
      </div>
    );
  }

  return null;
}

export default function AgentPage() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([]);
  const [currentEvents, setCurrentEvents] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [history, currentEvents]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');
    setIsStreaming(true);

    const userTurn = { role: 'user', content: userMessage };
    setHistory(prev => [...prev, userTurn]);
    setCurrentEvents([]);

    const streamAccumulator = [];

    try {
      const response = await api.runAgent(userMessage);

      if (!response.ok) {
        let errMsg = `Request failed with status ${response.status}`;
        try {
          const errJson = await response.json();
          errMsg = errJson.detail || errMsg;
        } catch {
          const errText = await response.text();
          if (errText) errMsg = errText;
        }
        throw new Error(errMsg);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEventType = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event:')) {
            currentEventType = trimmed.slice(6).trim();
          } else if (trimmed.startsWith('data:')) {
            const rawJson = trimmed.slice(5).trim();
            try {
              const payload = JSON.parse(rawJson);
              const eventType = currentEventType || payload.type || 'message';
              const eventData = payload.data !== undefined ? payload.data : payload;
              const newEvent = { type: eventType, data: eventData };

              streamAccumulator.push(newEvent);
              setCurrentEvents([...streamAccumulator]);
            } catch {
              // Ignore partial JSON
            }
            currentEventType = null;
          }
        }
      }

      if (streamAccumulator.length > 0) {
        setHistory(prev => [...prev, { role: 'agent', events: streamAccumulator }]);
      }
      setCurrentEvents([]);
    } catch (err) {
      const errorEvent = {
        type: 'error',
        data: { message: `Connection error: ${err.message}` },
      };
      setHistory(prev => [...prev, { role: 'agent', events: [errorEvent] }]);
      setCurrentEvents([]);
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

  const handleQuickPrompt = (prompt) => {
    setInput(prompt);
    inputRef.current?.focus();
  };

  const hasMessages = history.length > 0 || currentEvents.length > 0;

  return (
    <div className="agent-page-container fade-in">
      <div className="agent-page-header">
        <div className="agent-page-title">
          <div className="agent-page-avatar">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
              <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#ffffff" />
              <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
            </svg>
          </div>
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
        {!hasMessages && (
          <div className="agent-empty-state">
            <div className="agent-empty-icon">
              <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="14" stroke="#6ee7b7" strokeWidth="2" />
                <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#6ee7b7" />
                <circle cx="18.5" cy="14.5" r="9.5" fill="#0b0f19" />
              </svg>
            </div>
            <h3>DevSecOps AI Mentor</h3>
            <p>I am your AI agent that can provision infrastructure, write and commit GitHub action pipelines, and debug deployments. How can I help you today?</p>
            <div className="quick-prompts">
              {quickPrompts.map((prompt, i) => (
                <button
                  key={i}
                  className="quick-prompt-btn"
                  onClick={() => handleQuickPrompt(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* History Turns */}
        {history.map((item, idx) => {
          if (item.role === 'user') {
            return (
              <div key={`msg-${idx}`} className="agent-msg agent-msg-user">
                <span className="agent-msg-icon">{EventIcons.user}</span>
                <div className="agent-msg-body">
                  <span className="agent-msg-label">You</span>
                  <p>{item.content}</p>
                </div>
              </div>
            );
          }
          if (item.role === 'agent' && item.events) {
            return item.events.map((ev, evIdx) => (
              <AgentMessage key={`hist-${idx}-${evIdx}`} event={ev} />
            ));
          }
          return null;
        })}

        {/* Active Streaming Turn */}
        {currentEvents.map((event, i) => (
          <AgentMessage key={`active-${i}`} event={event} />
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
          {isStreaming ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: "pulse-dot 1.2s infinite" }}>
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a10 10 0 0 1 10 10" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </form>
    </div>
  );
}
