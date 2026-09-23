/**
 * ApprovalsDashboard — Admin/Guide view for managing pending HITL approval requests.
 *
 * Displays a table of pending mutating tool calls with approve/reject actions.
 */

import { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import './ApprovalsDashboard.css';

const STATUS_BADGES = {
  pending: { className: 'badge-warning', label: 'Pending' },
  approved: { className: 'badge-success', label: 'Approved' },
  rejected: { className: 'badge-error', label: 'Rejected' },
};

export default function ApprovalsDashboard() {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processing, setProcessing] = useState(null);
  const [tab, setTab] = useState('pending');
  const [expandedRow, setExpandedRow] = useState(null);

  const fetchActions = useCallback(async () => {
    try {
      setError(null);
      const data = tab === 'pending'
        ? await api.listPendingApprovals()
        : await api.listAllApprovals();
      setActions(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    fetchActions();
    const interval = setInterval(fetchActions, 10000);
    return () => clearInterval(interval);
  }, [fetchActions]);

  const handleApprove = async (actionId) => {
    setProcessing(actionId);
    try {
      await api.approveAction(actionId);
      await fetchActions();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (actionId) => {
    const reason = prompt('Reason for rejection (optional):');
    setProcessing(actionId);
    try {
      await api.rejectAction(actionId, reason || undefined);
      await fetchActions();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div className="approvals-page">
      <div className="approvals-header">
        <div>
          <h1 className="approvals-title">Approval Requests</h1>
          <p className="approvals-subtitle">
            Review and manage AI agent actions requiring human approval
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchActions}>
          ↻ Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="approvals-tabs">
        <button
          className={`tab-btn ${tab === 'pending' ? 'active' : ''}`}
          onClick={() => setTab('pending')}
        >
          ⏳ Pending
        </button>
        <button
          className={`tab-btn ${tab === 'all' ? 'active' : ''}`}
          onClick={() => setTab('all')}
        >
          📋 All Actions
        </button>
      </div>

      {error && (
        <div className="approvals-error">
          <span>❌</span> {error}
        </div>
      )}

      {loading ? (
        <div className="approvals-loading">
          <div className="spinner" />
          <p>Loading approval requests...</p>
        </div>
      ) : actions.length === 0 ? (
        <div className="approvals-empty">
          <div className="empty-icon">✅</div>
          <h3>No {tab === 'pending' ? 'pending' : ''} approval requests</h3>
          <p>
            {tab === 'pending'
              ? 'All mutating AI actions have been reviewed.'
              : 'No actions have been recorded yet.'}
          </p>
        </div>
      ) : (
        <div className="approvals-table-wrapper">
          <table className="approvals-table">
            <thead>
              <tr>
                <th>Tool</th>
                <th>Status</th>
                <th>Requested</th>
                <th>Details</th>
                {tab === 'pending' && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {actions.map((action) => {
                const badge = STATUS_BADGES[action.status] || STATUS_BADGES.pending;
                const isExpanded = expandedRow === action.id;

                return (
                  <>
                    <tr key={action.id} className={`action-row ${action.status}`}>
                      <td>
                        <code className="tool-name-cell">{action.tool_name}</code>
                      </td>
                      <td>
                        <span className={`badge ${badge.className}`}>
                          <span className="badge-dot" />
                          {badge.label}
                        </span>
                      </td>
                      <td className="td-time">
                        {new Date(action.created_at).toLocaleString()}
                      </td>
                      <td>
                        <button
                          className="btn-expand-row"
                          onClick={() => setExpandedRow(isExpanded ? null : action.id)}
                        >
                          {isExpanded ? 'Hide ▲' : 'View ▼'}
                        </button>
                      </td>
                      {tab === 'pending' && (
                        <td className="td-actions">
                          <button
                            className="btn btn-approve"
                            onClick={() => handleApprove(action.id)}
                            disabled={processing === action.id}
                          >
                            {processing === action.id ? '...' : '✓ Approve'}
                          </button>
                          <button
                            className="btn btn-reject"
                            onClick={() => handleReject(action.id)}
                            disabled={processing === action.id}
                          >
                            ✕ Reject
                          </button>
                        </td>
                      )}
                    </tr>
                    {isExpanded && (
                      <tr key={`${action.id}-detail`} className="detail-row">
                        <td colSpan={tab === 'pending' ? 5 : 4}>
                          <div className="detail-content">
                            <div className="detail-section">
                              <h4>Parameters</h4>
                              <pre>{JSON.stringify(action.tool_params, null, 2)}</pre>
                            </div>
                            {action.result && (
                              <div className="detail-section">
                                <h4>Result</h4>
                                <pre>{JSON.stringify(action.result, null, 2)}</pre>
                              </div>
                            )}
                            <div className="detail-meta">
                              <span>Action ID: {action.id}</span>
                              {action.reviewed_by && (
                                <span>Reviewed by: {action.reviewed_by}</span>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
