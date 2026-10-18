import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  HOURS_SAVED_PER_ACTIVE_SERVICE,
  calculateTotalHoursSaved,
  isActiveService,
  countActiveServices,
  calculateServiceEffort,
  PLATFORM_BENCHMARKS,
  DORA_BENCHMARKS,
} from './benchmarkMetrics.js';

describe('benchmarkMetrics Module', () => {
  describe('calculateTotalHoursSaved', () => {
    test('calculates active services × 1.25 hours correctly', () => {
      assert.equal(HOURS_SAVED_PER_ACTIVE_SERVICE, 1.25);
      assert.equal(calculateTotalHoursSaved(0), 0);
      assert.equal(calculateTotalHoursSaved(1), 1.25);
      assert.equal(calculateTotalHoursSaved(2), 2.5);
      assert.equal(calculateTotalHoursSaved(4), 5.0);
      assert.equal(calculateTotalHoursSaved(7), 8.75);
    });

    test('handles negative or invalid inputs safely', () => {
      assert.equal(calculateTotalHoursSaved(-5), 0);
      assert.equal(calculateTotalHoursSaved(null), 0);
      assert.equal(calculateTotalHoursSaved(undefined), 0);
      assert.equal(calculateTotalHoursSaved('invalid'), 0);
    });
  });

  describe('isActiveService & countActiveServices', () => {
    test('identifies active vs terminal inactive statuses', () => {
      assert.equal(isActiveService({ status: 'running' }), true);
      assert.equal(isActiveService({ status: 'active' }), true);
      assert.equal(isActiveService({ status: 'pending' }), true);
      assert.equal(isActiveService({ status: 'Running' }), true);
      assert.equal(isActiveService({}), true); // default active if unrecorded

      assert.equal(isActiveService({ status: 'failed' }), false);
      assert.equal(isActiveService({ status: 'stopped' }), false);
      assert.equal(isActiveService({ status: 'terminated' }), false);
      assert.equal(isActiveService({ status: 'deleted' }), false);
      assert.equal(isActiveService(null), false);
    });

    test('counts active services in an array', () => {
      const services = [
        { id: 1, status: 'running' },
        { id: 2, status: 'failed' },
        { id: 3, status: 'active' },
        { id: 4, status: 'stopped' },
        { id: 5, status: 'pending' },
      ];
      assert.equal(countActiveServices(services), 3);
      assert.equal(countActiveServices([]), 0);
      assert.equal(countActiveServices(null), 0);
    });
  });

  describe('calculateServiceEffort', () => {
    test('calculates base effort for default python stateless service', () => {
      const effort = calculateServiceEffort({
        language: 'python',
        framework: 'FastAPI',
        db_type: 'none',
        replicas: 1,
      });

      assert.ok(effort.manualTimeMinutes >= 60);
      assert.equal(effort.devhubTimeMinutes, 1);
      assert.ok(effort.timeSavedHours > 0);
      assert.ok(effort.boilerplateAvoidedLines > 150);
      assert.equal(effort.devhubSteps, 1);
    });

    test('scales effort up when adding database and complex language', () => {
      const simple = calculateServiceEffort({
        language: 'python',
        framework: 'Flask',
        db_type: 'none',
        replicas: 1,
      });

      const complex = calculateServiceEffort({
        language: 'java',
        framework: 'Spring Boot',
        db_type: 'postgres',
        replicas: 4,
      });

      assert.ok(complex.manualTimeMinutes > simple.manualTimeMinutes);
      assert.ok(complex.boilerplateAvoidedLines > simple.boilerplateAvoidedLines);
      assert.ok(complex.timeSavedHours > simple.timeSavedHours);
      assert.ok(complex.manualSteps > simple.manualSteps);
    });

    test('scales effort with replica count changes', () => {
      const rep1 = calculateServiceEffort({ language: 'go', db_type: 'postgres', replicas: 1 });
      const rep5 = calculateServiceEffort({ language: 'go', db_type: 'postgres', replicas: 5 });

      assert.ok(rep5.manualTimeMinutes > rep1.manualTimeMinutes);
      assert.ok(rep5.boilerplateAvoidedLines > rep1.boilerplateAvoidedLines);
    });
  });

  describe('PLATFORM_BENCHMARKS & DORA_BENCHMARKS', () => {
    test('contains required 4 benchmark comparisons', () => {
      const ids = PLATFORM_BENCHMARKS.map((b) => b.id);
      assert.ok(ids.includes('deployment_time'));
      assert.ok(ids.includes('boilerplate'));
      assert.ok(ids.includes('failure_rate'));
      assert.ok(ids.includes('tool_usage'));

      PLATFORM_BENCHMARKS.forEach((b) => {
        assert.ok(b.title);
        assert.ok(b.manual.value);
        assert.ok(b.devhub.value);
        assert.ok(b.improvement);
      });
    });

    test('contains DORA metrics definitions', () => {
      assert.equal(DORA_BENCHMARKS.length, 4);
      const names = DORA_BENCHMARKS.map((d) => d.name);
      assert.ok(names.includes('Deployment Frequency'));
      assert.ok(names.includes('Lead Time for Changes'));
      assert.ok(names.includes('Change Failure Rate'));
      assert.ok(names.includes('Time to Restore Service (MTTR)'));
    });
  });
});
