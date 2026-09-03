import { describe, it, expect } from 'vitest';
import {
  SAFETY_STATES,
  SAFETY_STATE_LABELS,
  SAFETY_STATE_COLORS,
  EVIDENCE_STATUSES,
  EVIDENCE_STATUS_LABELS,
  EVIDENCE_SOURCES,
  EVIDENCE_SOURCE_LABELS,
} from '@/types/safety';
import type { SafetyState, EvidenceStatus, EvidenceSource } from '@/types/safety';

describe('SafetyState types', () => {
  it('has all six safety states', () => {
    expect(SAFETY_STATES).toHaveLength(6);
    expect(SAFETY_STATES).toContain('CLEAR');
    expect(SAFETY_STATES).toContain('WATCH');
    expect(SAFETY_STATES).toContain('PAUSE');
    expect(SAFETY_STATES).toContain('VERIFY');
    expect(SAFETY_STATES).toContain('PROTECT');
    expect(SAFETY_STATES).toContain('RECOVERY');
  });

  it('has labels for every safety state', () => {
    for (const state of SAFETY_STATES) {
      expect(SAFETY_STATE_LABELS[state]).toBeTruthy();
      expect(typeof SAFETY_STATE_LABELS[state]).toBe('string');
    }
  });

  it('has color tokens for every safety state', () => {
    for (const state of SAFETY_STATES) {
      expect(SAFETY_STATE_COLORS[state]).toContain('var(--lumina-');
    }
  });

  it('CLEAR maps to recovery color (green/teal)', () => {
    expect(SAFETY_STATE_COLORS.CLEAR).toContain('recovery');
  });

  it('WATCH maps to warning color (amber)', () => {
    expect(SAFETY_STATE_COLORS.WATCH).toContain('warning');
  });

  it('PAUSE maps to danger color (crimson)', () => {
    expect(SAFETY_STATE_COLORS.PAUSE).toContain('danger');
  });

  it('VERIFY maps to warning color (amber)', () => {
    expect(SAFETY_STATE_COLORS.VERIFY).toContain('warning');
  });

  it('PROTECT maps to danger color (crimson)', () => {
    expect(SAFETY_STATE_COLORS.PROTECT).toContain('danger');
  });

  it('RECOVERY maps to investigation color (violet)', () => {
    expect(SAFETY_STATE_COLORS.RECOVERY).toContain('investigation');
  });

  it('SafetyState type is assignable to expected values', () => {
    const state: SafetyState = 'CLEAR';
    expect(state).toBe('CLEAR');
  });
});

describe('EvidenceStatus types', () => {
  it('has all six evidence statuses', () => {
    expect(EVIDENCE_STATUSES).toHaveLength(6);
    expect(EVIDENCE_STATUSES).toContain('OBSERVED');
    expect(EVIDENCE_STATUSES).toContain('USER_CONFIRMED');
    expect(EVIDENCE_STATUSES).toContain('UNKNOWN');
    expect(EVIDENCE_STATUSES).toContain('NOT_AVAILABLE');
    expect(EVIDENCE_STATUSES).toContain('NOT_PERMITTED');
    expect(EVIDENCE_STATUSES).toContain('INFERRED');
  });

  it('has labels for every evidence status', () => {
    for (const status of EVIDENCE_STATUSES) {
      expect(EVIDENCE_STATUS_LABELS[status]).toBeTruthy();
    }
  });

  it('EvidenceStatus type is assignable to expected values', () => {
    const status: EvidenceStatus = 'OBSERVED';
    expect(status).toBe('OBSERVED');
  });
});

describe('EvidenceSource types', () => {
  it('has all five evidence sources', () => {
    expect(EVIDENCE_SOURCES).toHaveLength(5);
    expect(EVIDENCE_SOURCES).toContain('DEVICE');
    expect(EVIDENCE_SOURCES).toContain('USER');
    expect(EVIDENCE_SOURCES).toContain('SYSTEM');
    expect(EVIDENCE_SOURCES).toContain('MODEL');
    expect(EVIDENCE_SOURCES).toContain('RULE');
  });

  it('has labels for every evidence source', () => {
    for (const source of EVIDENCE_SOURCES) {
      expect(EVIDENCE_SOURCE_LABELS[source]).toBeTruthy();
    }
  });

  it('EvidenceSource type is assignable to expected values', () => {
    const source: EvidenceSource = 'USER';
    expect(source).toBe('USER');
  });
});
