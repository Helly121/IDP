/**
 * MultiStepForm — Premium animated project creation wizard.
 *
 * Steps:
 *   1. Service Info (name, description)
 *   2. Tech Stack (language, framework)
 *   3. Infrastructure (database, replicas)
 *   4. Review & Submit
 */

import { useState, useCallback } from 'react';
import api from '../../api/client';
import './MultiStepForm.css';

const LANGUAGES = [
  { value: 'python', label: 'Python', icon: '🐍' },
  { value: 'javascript', label: 'JavaScript', icon: '⚡' },
  { value: 'typescript', label: 'TypeScript', icon: '💎' },
  { value: 'java', label: 'Java', icon: '☕' },
  { value: 'go', label: 'Go', icon: '🔷' },
  { value: 'rust', label: 'Rust', icon: '🦀' },
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
  { value: 'postgres', label: 'PostgreSQL', icon: '🐘', desc: 'Relational, ACID-compliant' },
  { value: 'mongodb', label: 'MongoDB', icon: '🍃', desc: 'Document store, flexible schema' },
  { value: 'redis', label: 'Redis', icon: '⚡', desc: 'In-memory cache & store' },
  { value: 'none', label: 'None', icon: '∅', desc: 'No database needed' },
];

const STEPS = [
  { id: 1, title: 'Service Info', icon: '📋' },
  { id: 2, title: 'Tech Stack', icon: '⚙️' },
  { id: 3, title: 'Infrastructure', icon: '☁️' },
  { id: 4, title: 'Review', icon: '✓' },
];

export default function MultiStepForm() {
  const [step, setStep] = useState(1);
  const [direction, setDirection] = useState('right');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState({});

  const [formData, setFormData] = useState({
    service_name: '',
    description: '',
    language: '',
    framework: '',
    db_type: 'none',
    replicas: 1,
  });

  const updateField = useCallback((field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
  }, []);

  // ── Validation ──────────────────────────────────────────────
  const validateStep = (stepNum) => {
    const errs = {};
    if (stepNum === 1) {
      if (!formData.service_name.trim()) {
        errs.service_name = 'Service name is required';
      } else if (!/^[a-z][a-z0-9-]{0,98}[a-z0-9]$/.test(formData.service_name)) {
        errs.service_name = 'Must be lowercase, start with a letter, use hyphens only (e.g., my-api)';
      }
    }
    if (stepNum === 2) {
      if (!formData.language) errs.language = 'Select a language';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const nextStep = () => {
    if (validateStep(step)) {
      setDirection('right');
      setStep((s) => Math.min(s + 1, 4));
    }
  };

  const prevStep = () => {
    setDirection('left');
    setStep((s) => Math.max(s - 1, 1));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        ...formData,
        framework: formData.framework === 'None' ? null : formData.framework?.toLowerCase(),
      };
      const res = await api.createProject(payload);
      setResult(res);
      setDirection('right');
      setStep(5); // Success view
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
      language: '',
      framework: '',
      db_type: 'none',
      replicas: 1,
    });
    setStep(1);
    setResult(null);
    setErrors({});
  };

  // ── Cost estimate preview ───────────────────────────────────
  const estimateCost = () => {
    const baseCost = formData.replicas * 2.5;
    const dbCosts = { postgres: 10, mongodb: 12, redis: 5, none: 0 };
    return (baseCost + (dbCosts[formData.db_type] || 0)).toFixed(2);
  };

  return (
    <div className="msf-container animate-fade-in">
      {/* ── Progress Bar ─────────────────────────────────────── */}
      {step <= 4 && (
        <div className="msf-progress">
          {STEPS.map((s, i) => (
            <div
              key={s.id}
              className={`msf-progress-step ${step >= s.id ? 'active' : ''} ${step === s.id ? 'current' : ''}`}
            >
              <div className="msf-progress-dot">
                {step > s.id ? '✓' : s.icon}
              </div>
              <span className="msf-progress-label">{s.title}</span>
              {i < STEPS.length - 1 && (
                <div className={`msf-progress-line ${step > s.id ? 'filled' : ''}`} />
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Form Steps ───────────────────────────────────────── */}
      <div className="msf-body glass-card">
        <div
          className={`msf-step-content ${direction === 'right' ? 'animate-slide-left' : 'animate-slide-right'}`}
          key={step}
        >
          {/* Step 1: Service Info */}
          {step === 1 && (
            <div className="msf-step">
              <div className="msf-step-header">
                <h2 className="msf-step-title">Name Your Service</h2>
                <p className="msf-step-subtitle">
                  Choose a unique, DNS-safe name for your cloud service.
                </p>
              </div>
              <div className="msf-fields">
                <div className="form-group">
                  <label className="form-label" htmlFor="service_name">
                    Service Name *
                  </label>
                  <input
                    id="service_name"
                    className={`form-input ${errors.service_name ? 'error' : ''}`}
                    type="text"
                    placeholder="e.g., my-flask-api"
                    value={formData.service_name}
                    onChange={(e) => updateField('service_name', e.target.value.toLowerCase())}
                  />
                  {errors.service_name && (
                    <span className="form-error">{errors.service_name}</span>
                  )}
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="description">
                    Description (optional)
                  </label>
                  <input
                    id="description"
                    className="form-input"
                    type="text"
                    placeholder="Brief description of your project"
                    value={formData.description}
                    onChange={(e) => updateField('description', e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Tech Stack */}
          {step === 2 && (
            <div className="msf-step">
              <div className="msf-step-header">
                <h2 className="msf-step-title">Choose Your Stack</h2>
                <p className="msf-step-subtitle">
                  Select the language and framework for your application.
                </p>
              </div>
              <div className="msf-fields">
                <div className="form-group">
                  <label className="form-label">Language *</label>
                  <div className="msf-option-grid">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.value}
                        type="button"
                        className={`msf-option-card ${formData.language === lang.value ? 'selected' : ''}`}
                        onClick={() => {
                          updateField('language', lang.value);
                          updateField('framework', '');
                        }}
                      >
                        <span className="msf-option-icon">{lang.icon}</span>
                        <span className="msf-option-label">{lang.label}</span>
                      </button>
                    ))}
                  </div>
                  {errors.language && (
                    <span className="form-error">{errors.language}</span>
                  )}
                </div>

                {formData.language && (
                  <div className="form-group animate-fade-in">
                    <label className="form-label" htmlFor="framework">Framework</label>
                    <select
                      id="framework"
                      className="form-select"
                      value={formData.framework}
                      onChange={(e) => updateField('framework', e.target.value)}
                    >
                      <option value="">Select a framework...</option>
                      {(FRAMEWORKS[formData.language] || []).map((fw) => (
                        <option key={fw} value={fw}>{fw}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Infrastructure */}
          {step === 3 && (
            <div className="msf-step">
              <div className="msf-step-header">
                <h2 className="msf-step-title">Configure Infrastructure</h2>
                <p className="msf-step-subtitle">
                  Select database and scaling options for your deployment.
                </p>
              </div>
              <div className="msf-fields">
                <div className="form-group">
                  <label className="form-label">Database</label>
                  <div className="msf-db-grid">
                    {DATABASES.map((db) => (
                      <button
                        key={db.value}
                        type="button"
                        className={`msf-db-card ${formData.db_type === db.value ? 'selected' : ''}`}
                        onClick={() => updateField('db_type', db.value)}
                      >
                        <span className="msf-db-icon">{db.icon}</span>
                        <span className="msf-db-label">{db.label}</span>
                        <span className="msf-db-desc">{db.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="replicas">
                    Replicas: <strong>{formData.replicas}</strong>
                  </label>
                  <input
                    id="replicas"
                    className="msf-slider"
                    type="range"
                    min="1"
                    max="10"
                    value={formData.replicas}
                    onChange={(e) => updateField('replicas', parseInt(e.target.value))}
                  />
                  <div className="msf-slider-labels">
                    <span>1</span>
                    <span>5</span>
                    <span>10</span>
                  </div>
                </div>

                <div className="msf-cost-preview glass">
                  <span className="msf-cost-label">Estimated Monthly Cost</span>
                  <span className="msf-cost-value">${estimateCost()}</span>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Review */}
          {step === 4 && (
            <div className="msf-step">
              <div className="msf-step-header">
                <h2 className="msf-step-title">Review & Deploy</h2>
                <p className="msf-step-subtitle">
                  Confirm your project configuration before provisioning.
                </p>
              </div>
              <div className="msf-review">
                <div className="msf-review-grid">
                  <ReviewItem label="Service Name" value={formData.service_name} />
                  <ReviewItem label="Description" value={formData.description || '—'} />
                  <ReviewItem
                    label="Language"
                    value={LANGUAGES.find((l) => l.value === formData.language)?.label}
                  />
                  <ReviewItem label="Framework" value={formData.framework || 'None'} />
                  <ReviewItem
                    label="Database"
                    value={DATABASES.find((d) => d.value === formData.db_type)?.label}
                  />
                  <ReviewItem label="Replicas" value={formData.replicas} />
                  <ReviewItem label="Est. Cost" value={`$${estimateCost()}/mo`} highlight />
                  <ReviewItem label="Namespace" value={`idp-${formData.service_name}`} />
                </div>
                {errors.submit && (
                  <div className="msf-error-banner">{errors.submit}</div>
                )}
              </div>
            </div>
          )}

          {/* Step 5: Success */}
          {step === 5 && result && (
            <div className="msf-step msf-success">
              <div className="msf-success-icon animate-scale-in">🚀</div>
              <h2 className="msf-step-title">Project Created!</h2>
              <p className="msf-step-subtitle">
                Your project <strong>{result.project?.service_name}</strong> is being provisioned.
              </p>
              <div className="msf-review-grid" style={{ marginTop: '1.5rem' }}>
                <ReviewItem label="Project ID" value={result.project?.id?.slice(0, 8) + '…'} />
                <ReviewItem label="Status" value={result.status} highlight />
                <ReviewItem label="Namespace" value={result.namespace} />
                <ReviewItem label="Cost" value={`$${result.cost_estimate}/mo`} />
              </div>
              <button className="btn btn-primary btn-lg" onClick={resetForm} style={{ marginTop: '2rem' }}>
                Create Another Project
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Navigation ───────────────────────────────────────── */}
      {step <= 4 && (
        <div className="msf-nav">
          <button
            className="btn btn-secondary"
            onClick={prevStep}
            disabled={step === 1}
          >
            ← Back
          </button>

          {step < 4 ? (
            <button className="btn btn-primary" onClick={nextStep}>
              Continue →
            </button>
          ) : (
            <button
              className="btn btn-primary btn-lg"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <span className="msf-spinner" />
              ) : (
                '🚀 Deploy Project'
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewItem({ label, value, highlight }) {
  return (
    <div className={`msf-review-item ${highlight ? 'highlight' : ''}`}>
      <span className="msf-review-label">{label}</span>
      <span className="msf-review-value">{value}</span>
    </div>
  );
}
