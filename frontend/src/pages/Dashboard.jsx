/**
 * Dashboard — DevHub (Internal Developer Platform)
 * Exact Spotify Portal Hero, Portal Ring, and Curved Horizon Sections
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import './Dashboard.css';

const STATS = [
  {
    label: 'Software Catalog',
    value: 'Automated',
    sub: 'Centralized Microservices',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="16" height="16" x="4" y="4" rx="2" />
        <rect width="6" height="6" x="9" y="9" rx="1" />
        <path d="M15 2v2M9 2v2M20 15h2M20 9h2M9 20v2M15 20v2M2 9h2M2 15h2" />
      </svg>
    ),
  },
  {
    label: 'Kubernetes GitOps',
    value: 'Active',
    sub: 'ArgoCD Sync Engine',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="m4.93 4.93 4.24 4.24M14.83 9.17l4.24-4.24M14.83 14.83l4.24 4.24M9.17 14.83l-4.24 4.24" />
      </svg>
    ),
  },
  {
    label: 'Platform Uptime',
    value: '99.9%',
    sub: 'High Availability',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
  {
    label: 'AI Manifest Generator',
    value: 'Gemini 1.5',
    sub: 'Prompt-to-K8s YAML',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      </svg>
    ),
  },
];

const FEATURES = [
  {
    title: 'Self-Service Provisioning',
    desc: 'Empower developers to create standardized services, namespaces, and persistence tiers in under 60 seconds.',
    tag: 'CATALOG',
    link: '/new-project',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1ed760" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
    ),
  },
  {
    title: 'AI Kubernetes Synthesis',
    desc: 'Generate optimized Deployment, Service, and Ingress manifests powered by Google Gemini API.',
    tag: 'INTELLIGENCE',
    link: '/new-project',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1ed760" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    ),
  },
  {
    title: 'Automated Log Diagnostics',
    desc: 'Deep inspection of runtime error traces to pinpoint failure root causes and suggest remediations.',
    tag: 'DIAGNOSTICS',
    link: '/new-project',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1ed760" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.3-4.3" />
      </svg>
    ),
  },
];

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [projects, setProjects] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projectsError, setProjectsError] = useState('');

  const loadProjects = async () => {
    try {
      const data = await api.listProjects();
      if (!Array.isArray(data)) {
        throw new Error('The services response was invalid.');
      }
      setProjects(data);
      setProjectsError('');
    } catch (err) {
      setProjectsError(err.message || 'Unable to load services.');
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    api.healthCheck()
      .then((data) => {
        setHealth(data);
        setLoadingHealth(false);
      })
      .catch(() => {
        setHealth({ status: 'offline', database: 'disconnected' });
        setLoadingHealth(false);
      });
  }, []);

  useEffect(() => {
    let active = true;
    api.listProjects()
      .then((data) => {
        if (!Array.isArray(data)) {
          throw new Error('The services response was invalid.');
        }
        if (active) {
          setProjects(data);
          setProjectsError('');
        }
      })
      .catch((err) => {
        if (active) setProjectsError(err.message || 'Unable to load services.');
      })
      .finally(() => {
        if (active) setLoadingProjects(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const retryProjects = () => {
    setLoadingProjects(true);
    setProjectsError('');
    loadProjects();
  };

  return (
    <div className="dash-root">
      {/* ── SECTION 1: Exact Spotify Portal Hero Ring ──────────── */}
      <section className="portal-hero-section">
        {/* Glowing Portal Ring Background */}
        <div className="portal-ring-wrapper">
          <div className="portal-glow-halo"></div>
          <div className="portal-ring-center">
            {/* Center Eclipse Emblem */}
            <div className="portal-center-icon">
              <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
                <path
                  d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z"
                  fill="#ffffff"
                />
                <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
              </svg>
            </div>

            {/* Headline */}
            <h1 className="portal-hero-headline">
              DevHub Portal <br />
              <span className="portal-hero-subhead">for Platform Engineering</span>
            </h1>

            {/* Subtitle */}
            <p className="portal-hero-desc">
              Get an internal developer portal built for high-velocity software engineering,
              self-service cloud provisioning, and AI automation.
            </p>

            {/* Mint Green Pill CTA Button */}
            <div className="portal-hero-cta">
              <Link to="/new-project" className="btn btn-primary btn-pill-lg">
                Create Service
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="container services-section" aria-labelledby="services-title">
        <div className="services-section-header">
          <div>
            <span className="section-kicker">SERVICE CATALOG</span>
            <h2 className="section-title" id="services-title">Your Services &amp; Deployments</h2>
          </div>
          {!loadingProjects && !projectsError && projects.length > 0 && (
            <Link to="/new-project" className="btn btn-secondary">Create Service</Link>
          )}
        </div>

        {loadingProjects ? (
          <div className="services-state" role="status">Loading your services...</div>
        ) : projectsError ? (
          <div className="services-state services-state-error" role="alert">
            <p>{projectsError}</p>
            <button className="btn btn-secondary" onClick={retryProjects}>Try Again</button>
          </div>
        ) : projects.length === 0 ? (
          <div className="services-state services-empty-state">
            <h3>No services yet</h3>
            <p>Create your first service to see its deployment configuration here.</p>
            <Link to="/new-project" className="btn btn-primary">Create Your First Service</Link>
          </div>
        ) : (
          <div className="services-grid">
            {projects.map((project) => (
              <article className="service-card" key={project.id}>
                <div className="service-card-heading">
                  <div>
                    <h3>{project.service_name}</h3>
                    <p className="service-namespace">
                      Namespace: {project.namespace || 'Not recorded'}
                    </p>
                  </div>
                  <span className={`service-status service-status-${project.status || 'unknown'}`}>
                    {project.status || 'Unknown'}
                  </span>
                </div>

                <div className="service-badges" aria-label="Service configuration">
                  <span className="service-badge">{project.language || 'Language not recorded'}</span>
                  <span className="service-badge">{project.framework || 'Framework not recorded'}</span>
                  <span className="service-badge">{project.db_type || 'Database not recorded'}</span>
                </div>

                <div className="service-metrics">
                  <div>
                    <span className="service-metric-label">Replicas</span>
                    <strong>{project.replicas ?? 'Not recorded'}</strong>
                  </div>
                  <div>
                    <span className="service-metric-label">Monthly cost</span>
                    <strong>
                      {project.cost_estimate == null
                        ? 'Not recorded'
                        : `$${Number(project.cost_estimate).toFixed(2)} / mo`}
                    </strong>
                  </div>
                </div>

                <Link
                  className="service-mentor-link"
                  to={`/agent?serviceId=${encodeURIComponent(project.id)}&serviceName=${encodeURIComponent(project.service_name)}`}
                >
                  Manage with AI Mentor
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* ── SECTION 2: "What is DevHub" (Screenshot 3 Style) ───── */}
      <section className="what-is-section container">
        <div className="what-is-content">
          <h2 className="what-is-title">What is DevHub</h2>
          <p className="what-is-desc">
            DevHub is an open internal developer platform (IDP) framework designed for academic & engineering
            organizations, powered by FastAPI, PostgreSQL, Kubernetes, and Google Gemini AI. Learn how DevHub transforms developer experience.
          </p>
          <div className="what-is-action">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary"
            >
              DevHub 101
            </a>
          </div>
        </div>
      </section>

      {/* ── SECTION 3: Platform Telemetry Metrics ───────────────── */}
      <section className="container telemetry-section">
        <div className="telemetry-grid">
          {STATS.map((stat) => (
            <div className="telemetry-card" key={stat.label}>
              <div className="telemetry-card-top">
                <span className="telemetry-icon">{stat.icon}</span>
                <span className="telemetry-pill">LIVE</span>
              </div>
              <div className="telemetry-val">{stat.value}</div>
              <div className="telemetry-label">{stat.label}</div>
              <div className="telemetry-sub">{stat.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── SECTION 4: Developer Capabilities ───────────────────── */}
      <section className="container capabilities-section">
        <div className="section-header-centered">
          <span className="section-kicker">WORKFLOWS</span>
          <h2 className="section-title">Everything you need to ship fast</h2>
        </div>

        <div className="capabilities-grid">
          {FEATURES.map((f) => (
            <Link to={f.link} className="capability-card" key={f.title}>
              <div className="cap-top">
                <div className="cap-icon-box">{f.icon}</div>
                <span className="cap-tag">{f.tag}</span>
              </div>
              <h3 className="cap-title">{f.title}</h3>
              <p className="cap-desc">{f.desc}</p>
              <div className="cap-footer">
                <span>Launch &gt;</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ── SECTION 5: Infrastructure Status Matrix ─────────────── */}
      <section className="container status-section">
        <div className="status-matrix-card">
          <div className="status-header">
            <h3 className="status-matrix-title">Infrastructure Cluster Telemetry</h3>
            <span className="badge badge-success">
              <span className="badge-dot"></span> All Systems Operational
            </span>
          </div>

          <div className="status-rows">
            <div className="status-row">
              <div className="status-row-info">
                <span className="status-row-name">FastAPI Core Orchestrator</span>
                <span className="status-row-desc">Port 8000 • Async API Engine</span>
              </div>
              <span className={`badge ${health?.status === 'healthy' ? 'badge-success' : 'badge-warning'}`}>
                {loadingHealth ? 'Checking...' : (health?.status === 'healthy' ? 'Operational' : 'Degraded')}
              </span>
            </div>

            <div className="status-row">
              <div className="status-row-info">
                <span className="status-row-name">Database Persistence Layer</span>
                <span className="status-row-desc">SQLAlchemy Async • SQLite / PostgreSQL</span>
              </div>
              <span className={`badge ${health?.database === 'connected' ? 'badge-success' : 'badge-error'}`}>
                {loadingHealth ? 'Checking...' : (health?.database === 'connected' ? 'Connected' : 'Unavailable')}
              </span>
            </div>

            <div className="status-row">
              <div className="status-row-info">
                <span className="status-row-name">ArgoCD Declarative GitOps</span>
                <span className="status-row-desc">Continuous Kubernetes Reconciliation</span>
              </div>
              <span className="badge badge-info">Active</span>
            </div>

            <div className="status-row">
              <div className="status-row-info">
                <span className="status-row-name">Kubernetes Namespace Isolation</span>
                <span className="status-row-desc">Resource Quotas & Pod Security Standards</span>
              </div>
              <span className="badge badge-info">Active</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 6: Curved Dark Dome (Screenshot 3 Horizon) ─── */}
      <section className="dome-section">
        <div className="dome-curve-wrapper">
          <div className="dome-curve-surface">
            <div className="container dome-content">
              <h2 className="dome-title">Let’s build!</h2>
              <p className="dome-subtitle">
                Create self-service cloud infrastructure and microservices with DevHub.
              </p>
              <div className="dome-cta">
                <Link to="/new-project" className="btn btn-primary btn-pill-lg">
                  Create Service
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
