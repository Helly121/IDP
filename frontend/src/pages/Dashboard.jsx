/**
 * Dashboard — Landing page with project overview cards and platform stats.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import './Dashboard.css';

const STATS = [
  { label: 'Active Projects', value: '—', icon: '📦', color: '#6366f1' },
  { label: 'Deployments', value: '—', icon: '🚀', color: '#8b5cf6' },
  { label: 'Uptime', value: '99.9%', icon: '💚', color: '#22c55e' },
  { label: 'AI Analyses', value: '—', icon: '🧠', color: '#f59e0b' },
];

const QUICK_ACTIONS = [
  {
    title: 'Create Project',
    desc: 'Launch the multi-step wizard to scaffold a new cloud service.',
    icon: '➕',
    to: '/new-project',
    primary: true,
  },
  {
    title: 'Generate Manifest',
    desc: 'Use AI to generate optimized Kubernetes YAML configurations.',
    icon: '📄',
    to: '/new-project',
  },
  {
    title: 'Analyze Logs',
    desc: 'Submit error logs for AI-powered diagnosis and remediation.',
    icon: '🔍',
    to: '/new-project',
  },
];

export default function Dashboard() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.healthCheck().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="dashboard page">
      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="dash-hero">
        <div className="dash-hero-content">
          <h1 className="dash-hero-title">
            Academic
            <span className="dash-hero-gradient"> Developer Platform</span>
          </h1>
          <p className="dash-hero-subtitle">
            Self-service cloud infrastructure provisioning for students, guides, and administrators.
            Deploy containerized applications with AI-powered automation.
          </p>
          <div className="dash-hero-actions">
            <Link to="/new-project" className="btn btn-primary btn-lg">
              🚀 New Project
            </Link>
            <a href="/docs" target="_blank" rel="noreferrer" className="btn btn-secondary btn-lg">
              📖 API Docs
            </a>
          </div>
        </div>
        <div className="dash-hero-visual">
          <div className="dash-orb dash-orb-1 animate-float"></div>
          <div className="dash-orb dash-orb-2 animate-float" style={{ animationDelay: '1s' }}></div>
          <div className="dash-orb dash-orb-3 animate-float" style={{ animationDelay: '2s' }}></div>
        </div>
      </section>

      {/* ── Stats ─────────────────────────────────────────────── */}
      <section className="dash-stats">
        {STATS.map((stat, i) => (
          <div
            className="dash-stat-card glass-card"
            key={stat.label}
            style={{ animationDelay: `${i * 0.1}s` }}
          >
            <span className="dash-stat-icon">{stat.icon}</span>
            <div className="dash-stat-info">
              <span className="dash-stat-value">{stat.value}</span>
              <span className="dash-stat-label">{stat.label}</span>
            </div>
          </div>
        ))}
      </section>

      {/* ── Quick Actions ─────────────────────────────────────── */}
      <section className="dash-actions">
        <h2 className="dash-section-title">Quick Actions</h2>
        <div className="dash-actions-grid">
          {QUICK_ACTIONS.map((action) => (
            <Link
              to={action.to}
              className={`dash-action-card glass-card ${action.primary ? 'primary' : ''}`}
              key={action.title}
            >
              <span className="dash-action-icon">{action.icon}</span>
              <h3 className="dash-action-title">{action.title}</h3>
              <p className="dash-action-desc">{action.desc}</p>
              <span className="dash-action-arrow">→</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── System Status ─────────────────────────────────────── */}
      <section className="dash-system">
        <h2 className="dash-section-title">System Status</h2>
        <div className="dash-system-card glass-card">
          <div className="dash-system-row">
            <span className="dash-system-label">Backend API</span>
            <span className={`badge ${health?.status === 'healthy' ? 'badge-success' : 'badge-warning'}`}>
              {health?.status || 'Checking…'}
            </span>
          </div>
          <div className="dash-system-row">
            <span className="dash-system-label">Database</span>
            <span className={`badge ${health?.database === 'connected' ? 'badge-success' : 'badge-error'}`}>
              {health?.database || 'Checking…'}
            </span>
          </div>
          <div className="dash-system-row">
            <span className="dash-system-label">ArgoCD Sync</span>
            <span className="badge badge-info">Phase 2</span>
          </div>
          <div className="dash-system-row">
            <span className="dash-system-label">Kubernetes Cluster</span>
            <span className="badge badge-info">Phase 2</span>
          </div>
        </div>
      </section>
    </div>
  );
}
