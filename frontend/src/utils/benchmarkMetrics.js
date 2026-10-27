/**
 * Benchmark Metrics & Quantitative IDP vs. Non-IDP Impact Analytics
 *
 * Provides standardized constants and dynamic estimation heuristics for:
 * 1. Engineering hours saved (1.25 hrs / active service)
 * 2. Visual Manual vs. DevHub comparisons (deployment time, boilerplate, failure rate, tool usage)
 * 3. Dynamic service creation effort benchmarking (language, framework, db, replicas)
 * 4. DORA metrics benchmarks
 *
 * NOTE: All benchmark values are engineering estimates based on standardized
 * cloud microservice onboarding models, not measured runtime telemetry.
 */

export const HOURS_SAVED_PER_ACTIVE_SERVICE = 1.25;

/**
 * Calculates total estimated engineering hours saved across active services.
 * Formula: active services × 1.25 hours
 *
 * @param {number} activeCount - Number of currently active services
 * @returns {number} Hours saved rounded to 2 decimal places
 */
export function calculateTotalHoursSaved(activeCount) {
  const count = Math.max(0, Number(activeCount) || 0);
  return Number((count * HOURS_SAVED_PER_ACTIVE_SERVICE).toFixed(2));
}

/**
 * Determines whether a service is considered active for platform impact calculation.
 * Services that are running, active, pending reconciliation, or without terminal failures
 * are counted as active workloads.
 *
 * @param {object} service
 * @returns {boolean}
 */
export function isActiveService(service) {
  if (!service || typeof service !== 'object') return false;
  const status = (service.status || 'active').toLowerCase().trim();
  const terminalInactiveStatuses = ['failed', 'stopped', 'terminated', 'deleted'];
  return !terminalInactiveStatuses.includes(status);
}

/**
 * Returns the count of active services from a service array.
 *
 * @param {Array} services
 * @returns {number}
 */
export function countActiveServices(services) {
  if (!Array.isArray(services)) return 0;
  return services.filter(isActiveService).length;
}

/**
 * Visual Manual vs. DevHub Platform Benchmarks for Dashboard
 */
export const PLATFORM_BENCHMARKS = [
  {
    id: 'deployment_time',
    title: 'Initial Deployment Time',
    category: 'Velocity',
    icon: 'clock',
    manual: {
      value: '~90 mins',
      numeric: 90,
      unit: 'minutes',
      label: 'Manual Provisioning',
      detail: 'Manual cluster manifests, ingress setup, DNS & CI/CD pipeline authoring',
    },
    devhub: {
      value: '~15 mins',
      numeric: 15,
      unit: 'minutes',
      label: 'DevHub Self-Service + GitOps',
      detail: 'Standardized golden-path synthesis and instant ArgoCD catalog registration',
    },
    improvement: '6x faster',
    savingsPerService: '1.25 hrs saved / service',
    pctReduction: 83,
  },
  {
    id: 'boilerplate',
    title: 'Infrastructure Boilerplate',
    category: 'Toil Reduction',
    icon: 'code',
    manual: {
      value: '~450 lines',
      numeric: 450,
      unit: 'lines',
      label: 'Manual YAML / IaC',
      detail: 'Handcrafted Deployment, Service, ConfigMaps, Secrets, Ingress, and RBAC manifests',
    },
    devhub: {
      value: '0 lines',
      numeric: 0,
      unit: 'lines',
      label: 'Automated Platform Scaffolding',
      detail: 'Zero manual YAML needed; standardized manifests generated dynamically',
    },
    improvement: '100% automated',
    savingsPerService: '~450 lines avoided / service',
    pctReduction: 100,
  },
  {
    id: 'failure_rate',
    title: 'Configuration Failure Rate',
    category: 'Reliability (DORA)',
    icon: 'shield',
    manual: {
      value: '~28%',
      numeric: 28,
      unit: '% error rate',
      label: 'Ad-hoc Deployments',
      detail: 'Schema mismatches, port conflicts, quota breaches, and missing security policies',
    },
    devhub: {
      value: '< 2%',
      numeric: 2,
      unit: '% error rate',
      label: 'Policy-Enforced Golden Paths',
      detail: 'Built-in schema validation, RBAC checks, and cluster-compatible specs',
    },
    improvement: '14x fewer errors',
    savingsPerService: '93% risk reduction',
    pctReduction: 93,
  },
  {
    id: 'tool_usage',
    title: 'Tool Usage & Context Switching',
    category: 'Developer Experience',
    icon: 'layers',
    manual: {
      value: '6 tools',
      numeric: 6,
      unit: 'tools',
      label: 'Fragmented DevOps Stack',
      detail: 'kubectl CLI, cloud console, Terraform, Vault, Helm, and CI/CD portal',
    },
    devhub: {
      value: '1 portal',
      numeric: 1,
      unit: 'portal',
      label: 'Unified IDP Experience',
      detail: 'Single pane of glass for catalog, self-service provisioning, and AI mentor diagnostics',
    },
    improvement: '83% less switching',
    savingsPerService: '1 unified interface',
    pctReduction: 83,
  },
];

/**
 * Standard DORA 4 Metrics Comparison
 */
export const DORA_BENCHMARKS = [
  {
    id: 'deployment_frequency',
    name: 'Deployment Frequency',
    manual: 'Bi-weekly / Monthly (Approval bottlenecks)',
    devhub: 'On-Demand / Multiple times per day',
    statusBadge: 'Elite Performer',
    benefit: 'High velocity without manual handoffs',
  },
  {
    id: 'lead_time',
    name: 'Lead Time for Changes',
    manual: '3 to 5 business days for infrastructure tickets',
    devhub: '< 15 minutes self-service to cluster',
    statusBadge: 'Elite Performer',
    benefit: 'Instant provisioning via GitOps',
  },
  {
    id: 'change_failure_rate',
    name: 'Change Failure Rate',
    manual: '25% - 30% rollback / hotfix frequency',
    devhub: '< 2% failure rate with automated policy checks',
    statusBadge: 'High Performer',
    benefit: 'Prevent misconfigurations before sync',
  },
  {
    id: 'mttr',
    name: 'Time to Restore Service (MTTR)',
    manual: '4+ hours (Manual triaging & distributed log search)',
    devhub: '< 15 minutes with AI Mentor root-cause analysis',
    statusBadge: 'Elite Performer',
    benefit: 'AI-assisted log diagnostics & remediation',
  },
];

// Language baseline adjustments
const LANGUAGE_EFFORT = {
  python: { manualMinutes: 15, boilerplateLines: 30, label: 'Python (Virtualenv, dependencies, WSGI/ASGI)' },
  javascript: { manualMinutes: 15, boilerplateLines: 30, label: 'JavaScript (Node modules, package.json, runner)' },
  typescript: { manualMinutes: 20, boilerplateLines: 45, label: 'TypeScript (Transpilation, tsconfig, build targets)' },
  go: { manualMinutes: 25, boilerplateLines: 50, label: 'Go (Multi-stage Dockerfile, CGO flags, static bin)' },
  rust: { manualMinutes: 35, boilerplateLines: 75, label: 'Rust (Cargo build cache, musl libc, binary strip)' },
  java: { manualMinutes: 40, boilerplateLines: 85, label: 'Java (JVM heap flags, cgroups v2, Maven/Gradle packaging)' },
};

// Database persistence tier adjustments
const DATABASE_EFFORT = {
  none: { manualMinutes: 0, boilerplateLines: 0, manualSteps: 0, label: 'Stateless Service' },
  redis: { manualMinutes: 20, boilerplateLines: 55, manualSteps: 3, label: 'Redis (Deployment, auth secret, client config)' },
  postgres: { manualMinutes: 35, boilerplateLines: 120, manualSteps: 5, label: 'PostgreSQL (StatefulSet, PVC, secrets, pooler)' },
  mongodb: { manualMinutes: 40, boilerplateLines: 140, manualSteps: 5, label: 'MongoDB (StatefulSet, replica set, volume claims)' },
};

/**
 * Calculates granular dynamic effort metrics for the Create Service wizard and Success screen.
 * Reacts dynamically to language, framework, database, and replica selections.
 *
 * @param {object} config - Service configuration { language, framework, db_type, replicas }
 * @returns {object} Calculated effort and savings metrics
 */
export function calculateServiceEffort(config = {}) {
  const language = (config.language || 'python').toLowerCase();
  const dbType = (config.db_type || 'none').toLowerCase();
  const replicas = Math.max(1, Math.min(10, parseInt(config.replicas, 10) || 1));

  // Base manual infrastructure baseline (Docker, Deployment, Service, Ingress, CI/CD pipeline)
  const baseManualMinutes = 60;
  const baseBoilerplateLines = 180;
  const baseManualSteps = 7;

  // Language & runtime adjustment
  const langEffort = LANGUAGE_EFFORT[language] || LANGUAGE_EFFORT.python;

  // Database tier adjustment
  const dbEffort = DATABASE_EFFORT[dbType] || DATABASE_EFFORT.none;

  // Replica & high availability adjustment
  // Multiple replicas require HPA, PodDisruptionBudget, anti-affinity, and probe tuning
  const replicaMinutes = (replicas - 1) * 4;
  const replicaBoilerplate = (replicas - 1) * 12;
  const replicaSteps = replicas > 1 ? 2 : 0;

  const totalManualMinutes = baseManualMinutes + langEffort.manualMinutes + dbEffort.manualMinutes + replicaMinutes;
  const totalBoilerplateLines = baseBoilerplateLines + langEffort.boilerplateLines + dbEffort.boilerplateLines + replicaBoilerplate;
  const totalManualSteps = baseManualSteps + dbEffort.manualSteps + replicaSteps;

  // DevHub effort (always 1-2 minutes, 0 manual boilerplate lines, 1 step submission)
  const devhubMinutes = 1;
  const devhubBoilerplateLines = 0;
  const devhubSteps = 1;

  const timeSavedMinutes = totalManualMinutes - devhubMinutes;
  const timeSavedHours = Number((timeSavedMinutes / 60).toFixed(1));

  return {
    manualTimeMinutes: totalManualMinutes,
    manualTimeFormatted: totalManualMinutes >= 60
      ? `${(totalManualMinutes / 60).toFixed(1)} hrs (${totalManualMinutes} mins)`
      : `${totalManualMinutes} mins`,
    devhubTimeMinutes: devhubMinutes,
    devhubTimeFormatted: '< 1 min',
    timeSavedHours,
    timeSavedFormatted: `${timeSavedHours} hrs`,
    boilerplateAvoidedLines: totalBoilerplateLines,
    devhubBoilerplateLines,
    manualSteps: totalManualSteps,
    devhubSteps,
    estimatedFailureRiskManual: '28%',
    estimatedFailureRiskDevHub: '< 2%',
    disclaimer: 'Estimates based on standardized microservice infrastructure benchmarks.',
  };
}
