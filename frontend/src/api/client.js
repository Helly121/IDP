/**
 * API client — Axios instance preconfigured for the FastAPI backend.
 * Base URL comes from VITE_API_BASE_URL environment variable.
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
  // ── Projects ──────────────────────────────────────────────
  createProject: (data) =>
    request('/api/v1/projects/create', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getProjectStatus: (projectId) =>
    request(`/api/v1/projects/${projectId}/status`),

  // ── AI ────────────────────────────────────────────────────
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

  // ── Health ────────────────────────────────────────────────
  healthCheck: () => request('/api/v1/health'),
};

export default api;
