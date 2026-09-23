/**
 * API client — Fetch wrapper preconfigured for the FastAPI backend.
 * Supports both standard JSON requests and SSE streaming for the agent.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Lightweight fetch wrapper with JSON defaults and error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  // Attach JWT if available
  const token = localStorage.getItem('idp_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

/** API client methods */
const api = {
  // ── Projects ─────────────────────────────────────────
  createProject: (data) =>
    request('/api/v1/projects/create', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getProjectStatus: (projectId) =>
    request(`/api/v1/projects/${projectId}/status`),

  // ── Agent (SSE Streaming) ────────────────────────────
  runAgent: (message, context = {}) => {
    const url = `${API_BASE}/api/v1/agent/run`;
    const token = localStorage.getItem('idp_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    // Return raw Response for SSE streaming (caller reads via ReadableStream)
    return fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        user_id: context.user_id || '00000000-0000-0000-0000-000000000001',
        project_id: context.project_id || null,
        session_id: context.session_id || null,
      }),
    });
  },

  // ── Approvals ────────────────────────────────────────
  listPendingApprovals: () =>
    request('/api/v1/approvals/pending'),

  listAllApprovals: (limit = 50) =>
    request(`/api/v1/approvals/all?limit=${limit}`),

  approveAction: (actionId, reviewerId) =>
    request(`/api/v1/approvals/${actionId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId }),
    }),

  rejectAction: (actionId, reviewerId, reason = null) =>
    request(`/api/v1/approvals/${actionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId, reason }),
    }),

  // ── Health ───────────────────────────────────────────
  healthCheck: () => request('/api/v1/health'),
};

export default api;
