/**
 * API client — Fetch wrapper preconfigured for the FastAPI backend.
 * Supports standard JSON requests, auth endpoints, and SSE streaming for the agent.
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
  // ── Auth ─────────────────────────────────────────────
  getAuthConfig: () =>
    request('/api/v1/auth/config'),

  register: (data) =>
    request('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  login: (data) =>
    request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  googleAuth: (idToken) =>
    request('/api/v1/auth/google', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken }),
    }),

  getMe: () =>
    request('/api/v1/auth/me'),

  listUsers: () =>
    request('/api/v1/auth/users'),

  updateUserRole: (userId, role) =>
    request(`/api/v1/auth/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  // ── Projects ─────────────────────────────────────────
  listProjects: () =>
    request('/api/v1/projects'),

  createProject: (data) =>
    request('/api/v1/projects/create', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getProjectStatus: (projectId) =>
    request(`/api/v1/projects/${projectId}/status`),

  // ── AI (Legacy) ──────────────────────────────────────
  generateManifest: (data) =>
    request('/api/v1/ai/manifest-generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  analyzeLogs: (data) =>
    request('/api/v1/ai/log-analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ── Agent (SSE Streaming) ────────────────────────────
  runAgent: (message, context = {}) => {
    const url = `${API_BASE}/api/v1/agent/run`;
    const token = localStorage.getItem('idp_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let resolvedUserId = context.user_id;
    if (!resolvedUserId) {
      try {
        const storedUser = JSON.parse(localStorage.getItem('idp_user') || '{}');
        resolvedUserId = storedUser.id || null;
      } catch {
        resolvedUserId = null;
      }
    }

    // Return raw Response for SSE streaming (caller reads via ReadableStream)
    return fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        user_id: resolvedUserId,
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

  approveAction: (actionId, reason = null) =>
    request(`/api/v1/approvals/${actionId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  rejectAction: (actionId, reason = null) =>
    request(`/api/v1/approvals/${actionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // ── Health ───────────────────────────────────────────
  healthCheck: () => request('/api/v1/health'),
};

export default api;
