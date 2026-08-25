/**
 * MultiStepForm — DevHub (Internal Developer Platform)
 * Exact Spotify Portal 2-Column "Try-Portal" Layout (Screenshot 1)
 */

import { useState, useCallback } from 'react';
import api from '../../api/client';
import './MultiStepForm.css';

const LANGUAGES = [
  { value: 'python', label: 'Python (FastAPI, Django, Flask)' },
  { value: 'javascript', label: 'JavaScript (Node.js, Express, Hono)' },
  { value: 'typescript', label: 'TypeScript (NestJS, Hono, Express)' },
  { value: 'go', label: 'Go (Gin, Echo, Fiber)' },
  { value: 'rust', label: 'Rust (Actix, Axum, Rocket)' },
  { value: 'java', label: 'Java (Spring Boot, Quarkus)' },
];

const FRAMEWORKS = {
  python: ['FastAPI', 'Django', 'Flask', 'None'],
  javascript: ['Express', 'NestJS', 'Hono', 'None'],
  typescript: ['Express', 'NestJS', 'Hono', 'None'],
  java: ['Spring Boot', 'Quarkus', 'Micronaut', 'None'],
  go: ['Gin', 'Echo', 'Fiber', 'None'],
  rust: ['Actix', 'Axum', 'Rocket', 'None'],
};

const DATABASES = [
  { value: 'postgres', label: 'PostgreSQL — Relational ACID (Dedicated)' },
  { value: 'mongodb', label: 'MongoDB — Document Store (Replica Set)' },
  { value: 'redis', label: 'Redis — In-Memory Cache (High-Throughput)' },
  { value: 'none', label: 'Stateless Service — No Database' },
];

export default function MultiStepForm() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState({});
  const [agreed, setAgreed] = useState(true);

  const [formData, setFormData] = useState({
    service_name: '',
    description: '',
    language: 'python',
    framework: 'FastAPI',
    db_type: 'postgres',
    replicas: 2,
  });

  const updateField = useCallback((field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
  }, []);

  const estimateCost = () => {
    const base = 15;
    const replicaCost = (formData.replicas || 1) * 10;
    const dbCost = formData.db_type === 'postgres' ? 25 : formData.db_type === 'mongodb' ? 30 : formData.db_type === 'redis' ? 15 : 0;
    return base + replicaCost + dbCost;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!formData.service_name.trim()) {
      errs.service_name = 'Service name is required';
    } else if (!/^[a-z][a-z0-9-]{0,98}[a-z0-9]$/.test(formData.service_name)) {
      errs.service_name = 'Must be lowercase, start with letter, use hyphens (e.g. order-service)';
    }

    if (!formData.language) {
      errs.language = 'Language selection is required';
    }

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        ...formData,
        framework: formData.framework === 'None' ? null : formData.framework?.toLowerCase(),
      };
      const res = await api.createProject(payload);
      setResult(res);
    } catch (err) {
      setErrors({ submit: err.message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      service_name: '',
      description: '',
      language: 'python',
      framework: 'FastAPI',
      db_type: 'postgres',
      replicas: 2,
    });
    setResult(null);
    setErrors({});
  };

  return (
    <div className="try-portal-container container">
      {/* ── Main 2-Column Outer Box (Screenshot 1) ─────────────── */}
      <div className="try-portal-box">
        {/* ── Left Column: Value Proposition & Quote ──────────── */}
        <div className="try-left-card">
          <div className="try-left-header">
            {/* Eclipse Logo Mark */}
            <div className="try-eclipse-icon">
              <svg width="36" height="36" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
                <path
                  d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z"
                  fill="#ffffff"
                />
                <circle cx="18.5" cy="14.5" r="9.5" fill="#12141c" />
              </svg>
            </div>

            <h2 className="try-left-title">
              See what DevHub can do for your engineering team
            </h2>

            <p className="try-left-desc">
              DevHub is an internal developer portal (IDP) powered by Kubernetes & AI —
              fully managed, automated, and customized for high-velocity software engineering.
            </p>
          </div>

          <div className="try-left-bullets">
            <h4 className="try-bullets-title">What to expect:</h4>
            <ul className="try-bullets-list">
              <li>• A tailored look at DevHub’s software catalog, namespaces, and AI capabilities</li>
              <li>• Best practices from platform teams who’ve already scaled microservices</li>
              <li>• Automated CI/CD pipelines and declarative GitOps delivery</li>
              <li>• Instant answers and AI diagnosis for your hardest cluster questions</li>
            </ul>
          </div>

          {/* Testimonial Quote Box */}
          <div className="try-testimonial-card">
            <span className="testimonial-role">Director of Platform Engineering</span>
            <p className="testimonial-quote">
              “DevHub is allowing us to actually surface cloud infrastructure that hasn’t been
              possible in the past, which is super exciting, all within the context of our applications.”
            </p>
            <div className="testimonial-company-pill">
              Academic IDP
            </div>
          </div>

          {/* Partner / Tech Bar */}
          <div className="try-tech-footer">
            <span className="tech-badge">FastAPI</span>
            <span className="tech-badge">PostgreSQL</span>
            <span className="tech-badge">Kubernetes</span>
            <span className="tech-badge">ArgoCD</span>
          </div>
        </div>

        {/* ── Right Column: Interactive Provisioning Form ──────── */}
        <div className="try-right-form">
          {result ? (
            /* Success State */
            <div className="try-success-view animate-fade-in">
              <div className="try-success-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#000000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>

              <h3 className="try-success-title">Service Provisioned Successfully!</h3>
              <p className="try-success-sub">
                Workload <strong>idp-{result.project?.service_name || formData.service_name}</strong> is now registered and reconciling in the cluster.
              </p>

              <div className="try-spec-summary">
                <div className="spec-row">
                  <span className="spec-label">Service ID</span>
                  <span className="spec-val">{result.project?.id?.slice(0, 12) || 'Generated'}...</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Namespace</span>
                  <span className="spec-val text-green">{result.namespace || `idp-${formData.service_name}`}</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Deployment Status</span>
                  <span className="spec-val text-green">{result.status || 'Active'}</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Monthly Allocation</span>
                  <span className="spec-val">${result.cost_estimate || estimateCost()} / mo</span>
                </div>
              </div>

              <button className="btn btn-pill-submit" onClick={resetForm} style={{ marginTop: '2rem' }}>
                Provision Another Service
              </button>
            </div>
          ) : (
            /* Main Form */
            <form onSubmit={handleSubmit} className="try-form-body">
              {/* Row 1: Service Name & Namespace */}
              <div className="try-form-row">
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="service_name">
                    Service Name*
                  </label>
                  <input
                    id="service_name"
                    className="form-input"
                    type="text"
                    placeholder="e.g. auth-service"
                    value={formData.service_name}
                    onChange={(e) => updateField('service_name', e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                    required
                  />
                  {errors.service_name && (
                    <span className="form-error">{errors.service_name}</span>
                  )}
                </div>

                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="namespace">
                    Target Namespace*
                  </label>
                  <input
                    id="namespace"
                    className="form-input"
                    type="text"
                    readOnly
                    value={`idp-${formData.service_name || 'service'}`}
                    style={{ background: '#f3f4f6', color: '#4b5563' }}
                  />
                </div>
              </div>

              {/* Row 2: Description */}
              <div className="form-group">
                <label className="form-label" htmlFor="description">
                  Workload Description*
                </label>
                <input
                  id="description"
                  className="form-input"
                  type="text"
                  placeholder="Primary responsibility and architectural scope..."
                  value={formData.description}
                  onChange={(e) => updateField('description', e.target.value)}
                />
              </div>

              {/* Row 3: Language & Framework */}
              <div className="try-form-row">
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="language">
                    Primary Language*
                  </label>
                  <select
                    id="language"
                    className="form-select"
                    value={formData.language}
                    onChange={(e) => {
                      updateField('language', e.target.value);
                      updateField('framework', (FRAMEWORKS[e.target.value] || [])[0] || 'None');
                    }}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="framework">
                    Framework Scaffolding*
                  </label>
                  <select
                    id="framework"
                    className="form-select"
                    value={formData.framework}
                    onChange={(e) => updateField('framework', e.target.value)}
                  >
                    {(FRAMEWORKS[formData.language] || ['None']).map((fw) => (
                      <option key={fw} value={fw}>
                        {fw}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Row 4: Database Tier */}
              <div className="form-group">
                <label className="form-label" htmlFor="db_type">
                  Database Persistence Tier*
                </label>
                <select
                  id="db_type"
                  className="form-select"
                  value={formData.db_type}
                  onChange={(e) => updateField('db_type', e.target.value)}
                >
                  {DATABASES.map((db) => (
                    <option key={db.value} value={db.value}>
                      {db.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Row 5: Pod Replicas */}
              <div className="form-group">
                <div className="try-slider-header">
                  <label className="form-label" htmlFor="replicas">
                    Kubernetes Pod Replicas: <strong>{formData.replicas} Pods</strong>
                  </label>
                  <span className="try-cost-badge">Est. ${estimateCost()} / mo</span>
                </div>
                <input
                  id="replicas"
                  type="range"
                  min="1"
                  max="10"
                  value={formData.replicas}
                  onChange={(e) => updateField('replicas', parseInt(e.target.value))}
                  style={{ width: '100%', accentColor: '#1ed760', cursor: 'pointer' }}
                />
              </div>

              {/* Agreement Checkbox (Screenshot 1 Style) */}
              <div className="try-checkbox-row">
                <input
                  type="checkbox"
                  id="agree"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  style={{ accentColor: '#1ed760', width: '18px', height: '18px', cursor: 'pointer' }}
                />
                <label htmlFor="agree" className="try-checkbox-label">
                  I agree to provision this cloud service in accordance with DevHub infrastructure governance and cluster resource policies.
                </label>
              </div>

              {/* Error Banner */}
              {errors.submit && (
                <div className="form-error" style={{ marginBottom: '1rem' }}>
                  {errors.submit}
                </div>
              )}

              {/* Mint Green Submit Pill Button (Screenshot 1 Style) */}
              <button
                type="submit"
                className="btn btn-pill-submit"
                disabled={isSubmitting || !agreed}
              >
                {isSubmitting ? 'Provisioning Cloud Workload...' : 'Submit'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
