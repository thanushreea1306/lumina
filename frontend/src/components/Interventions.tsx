/* ============================================================
   LUMINA Intervention Components
   ============================================================
   Shared primitives for VERIFY, PAUSE, PROTECT.
   ============================================================ */

import type { ReactNode } from 'react';
import type { SafetyState } from '@/types/safety';
import { SAFETY_STATE_LABELS } from '@/types/safety';

// ---- InterventionShell ----

export function InterventionShell({
  state: _state,
  children,
}: {
  state: SafetyState;
  children: ReactNode;
}) {
  void _state; // Used for future state-aware layout
  return (
    <div className="intervention-shell" data-testid="intervention-shell">
      {children}
    </div>
  );
}

// ---- InterventionHeader ----

export function InterventionHeader({
  state,
  icon,
  title,
  subtitle,
}: {
  state: SafetyState;
  icon: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="intervention-hero" data-state={state} role="status" aria-label={`Safety status: ${SAFETY_STATE_LABELS[state]}`}>
      <div className="intervention-icon" data-state={state} aria-hidden="true">
        {icon}
      </div>
      <h1 className="intervention-title">{title}</h1>
      <p className="intervention-subtitle">{subtitle}</p>
    </div>
  );
}

// ---- ReasonList ----

export function ReasonList({
  reasons,
  state,
}: {
  reasons: string[];
  state: SafetyState;
}) {
  if (reasons.length === 0) return null;

  return (
    <div className="guidance-card">
      <div className="guidance-card-title">Why This State</div>
      <ul className="reason-list" role="list" aria-label="Reasons for current safety state">
        {reasons.map((reason, i) => (
          <li key={i} className="reason-item">
            <span className="reason-dot" data-state={state} aria-hidden="true" />
            <span className="reason-text">{reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- SafetyGuidance ----

export function SafetyGuidance({
  title,
  items,
}: {
  title: string;
  items: Array<{ text: string; type: 'safe' | 'warn' }>;
}) {
  if (items.length === 0) return null;

  return (
    <div className="guidance-card">
      <div className="guidance-card-title">{title}</div>
      <ul className="guidance-list" role="list" aria-label={title}>
        {items.map((item, i) => (
          <li key={i} className="guidance-item">
            <span className={item.type === 'safe' ? 'guidance-check' : 'guidance-warn'} aria-hidden="true">
              {item.type === 'safe' ? '✓' : '✕'}
            </span>
            <span>{item.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- HighRiskActionList ----

export function HighRiskActionList({
  actions,
}: {
  actions: Array<{ action: string; status: string; description: string }>;
}) {
  if (actions.length === 0) return null;

  function formatActionName(action: string): string {
    return action
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function formatStatus(status: string): string {
    return status
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  return (
    <div className="guidance-card">
      <div className="guidance-card-title">High-Risk Actions</div>
      <ul className="high-risk-list" role="list" aria-label="High-risk actions detected">
        {actions.map((action, i) => (
          <li key={i} className="high-risk-item">
            <div>
              <div className="high-risk-label">{formatActionName(action.action)}</div>
              {action.description && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', marginTop: '2px' }}>
                  {action.description}
                </div>
              )}
            </div>
            <span className="high-risk-status" data-status={action.status}>
              {formatStatus(action.status)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- ResponseOptions ----

export function ResponseOptions({
  options,
  onSelect,
  submitting,
}: {
  options: Array<{
    action: string;
    response: string;
    label: string;
    description?: string;
    icon: string;
    variant: 'primary' | 'safe' | 'danger';
  }>;
  onSelect: (action: string, response: string) => void;
  submitting: boolean;
}) {
  return (
    <div className="response-options" role="group" aria-label="Available responses">
      {options.map((option) => (
        <button
          key={`${option.action}-${option.response}`}
          className={`response-btn response-btn-${option.variant}`}
          onClick={() => onSelect(option.action, option.response)}
          disabled={submitting}
          aria-label={option.label}
        >
          <span className="response-btn-icon" aria-hidden="true">{option.icon}</span>
          <div className="response-btn-label">
            <div>{option.label}</div>
            {option.description && (
              <div className="response-btn-desc">{option.description}</div>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

// ---- MissingInfoList ----

export function MissingInfoList({
  items,
}: {
  items: string[];
}) {
  if (items.length === 0) return null;

  return (
    <div className="guidance-card">
      <div className="guidance-card-title">Missing Information</div>
      <ul className="missing-info-list" role="list" aria-label="Missing information">
        {items.map((item, i) => (
          <li key={i} className="missing-info-item">
            <span className="missing-info-icon" aria-hidden="true">?</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
