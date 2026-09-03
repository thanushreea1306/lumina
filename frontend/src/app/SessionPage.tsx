/* ============================================================
   LUMINA Active Session
   ============================================================
   The real Session experience. Implements:
   - Session creation
   - Safety state display
   - Forensic safety check (observation submission)
   - Evidence count
   - Timeline
   - High-risk action indicators
   ============================================================ */

import { useState } from 'react';
import { useSessionState } from '@/hooks/useSessionState';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { CaseID } from '@/components/CaseID';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { Divider } from '@/components/Divider';
import {
  OBSERVATION_OPTIONS,
  CATEGORY_COLORS,
  CATEGORY_LABELS,
} from '@/lib/observations';
import type { SafetyState } from '@/types/safety';
import { SAFETY_STATE_COLORS } from '@/types/safety';

// ---- Helpers ----

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function stateDescription(state: SafetyState): string {
  switch (state) {
    case 'CLEAR': return 'No safety concerns detected.';
    case 'WATCH': return 'Observations recorded. Stay alert.';
    case 'VERIFY': return 'Verify the caller independently before proceeding.';
    case 'PAUSE': return 'Do not share codes, passwords, or money. Pause and verify.';
    case 'PROTECT': return 'Stop immediately. Verify independently through official channels.';
    case 'RECOVERY': return 'Secure your accounts and contact officials directly.';
  }
}

// ---- Session Creation View ----

function SessionCreationView({ onCreate, error }: { onCreate: () => void; error: string | null }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - 10rem)',
      padding: 'var(--space-8)',
      animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) both',
    }}>
      <Card elevated style={{ maxWidth: '32rem', width: '100%', textAlign: 'center' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-4)',
        }}>
          Forensic Safety Check
        </div>

        <h1 style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
        }}>
          Begin a Safety Session
        </h1>

        <p style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: 'var(--space-6)',
        }}>
          Start a session when you want LUMINA to help examine a potentially
          risky situation. You can report observations as they happen.
        </p>

        {error && (
          <div role="alert" style={{
            padding: 'var(--space-3) var(--space-4)',
            background: 'var(--lumina-danger-soft)',
            border: '1px solid rgba(224, 28, 43, 0.3)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-danger)',
            marginBottom: 'var(--space-4)',
          }}>
            {error}
          </div>
        )}

        <Button variant="primary" size="lg" onClick={onCreate} style={{ width: '100%' }}>
          Start Session
        </Button>
      </Card>
    </div>
  );
}

// ---- Observation Controls ----

function ObservationControls({
  onObservation,
  submitting,
  submittedTypes,
}: {
  onObservation: (type: string) => void;
  submitting: boolean;
  submittedTypes: Set<string>;
}) {
  // Group by category
  const categories = OBSERVATION_OPTIONS.reduce((acc, opt) => {
    if (!acc[opt.category]) acc[opt.category] = [];
    acc[opt.category].push(opt);
    return acc;
  }, {} as Record<string, typeof OBSERVATION_OPTIONS>);

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-5)',
      }}>
        <span
          aria-hidden="true"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-sm)',
            fontWeight: 800,
            color: 'var(--lumina-investigation)',
            background: 'var(--lumina-investigation-soft)',
            border: '1px solid rgba(155, 123, 219, 0.25)',
            borderRadius: 'var(--radius-md)',
            padding: '4px 10px',
          }}
        >
          01
        </span>
        <div>
          <h2 style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
          }}>
            What did you observe?
          </h2>
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            marginTop: 'var(--space-1)',
          }}>
            Select what actually happened. LUMINA will assess the situation.
          </p>
        </div>
      </div>

      {Object.entries(categories).map(([cat, options]) => (
        <div key={cat} style={{ marginBottom: 'var(--space-5)' }}>
          <div
            className="observation-category"
            style={{ color: CATEGORY_COLORS[cat] }}
          >
            {CATEGORY_LABELS[cat]}
          </div>
          <div className="session-observations">
            {options.map((opt) => {
              const isSubmitted = submittedTypes.has(opt.type);
              return (
                <button
                  key={opt.type}
                  className="observation-card"
                  aria-pressed={isSubmitted}
                  data-submitting={submitting && !isSubmitted}
                  onClick={() => {
                    if (!isSubmitted && !submitting) {
                      onObservation(opt.type);
                    }
                  }}
                  disabled={isSubmitted || submitting}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                    <div className="observation-indicator" aria-hidden="true" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 'var(--text-sm)',
                        fontWeight: 700,
                        color: isSubmitted ? 'var(--lumina-recovery)' : 'var(--lumina-text)',
                        marginBottom: '2px',
                      }}>
                        {opt.prompt}
                      </div>
                      <div style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--lumina-text-muted)',
                        lineHeight: 'var(--leading-normal)',
                      }}>
                        {opt.description}
                      </div>
                    </div>
                    <span
                      aria-hidden="true"
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: CATEGORY_COLORS[opt.category],
                        flexShrink: 0,
                        marginTop: '6px',
                      }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Session Timeline ----

function SessionTimeline({
  events,
}: {
  events: Array<{
    event_type: string;
    sequence: number;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
}) {
  if (events.length === 0) return null;

  const eventLabels: Record<string, string> = {
    SESSION_STARTED: 'Session started',
    CALL_STARTED: 'Call started',
    CALL_ACTIVE: 'Call active',
    USER_OBSERVATION: 'Observation recorded',
    HIGH_RISK_ACTION_REQUEST: 'High-risk action requested',
    USER_RESPONSE: 'User response',
    CALL_ENDED: 'Call ended',
    DECISION: 'Decision evaluated',
  };

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-4)',
      }}>
        <span
          aria-hidden="true"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-sm)',
            fontWeight: 800,
            color: 'var(--lumina-system)',
            background: 'var(--lumina-system-soft)',
            border: '1px solid rgba(94, 196, 212, 0.25)',
            borderRadius: 'var(--radius-md)',
            padding: '4px 10px',
          }}
        >
          02
        </span>
        <h2 style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
        }}>
          Timeline
        </h2>
      </div>

      <Card>
        <div className="session-timeline" role="list" aria-label="Session timeline">
          {events.map((event) => (
            <div key={event.sequence} className="session-timeline-item" role="listitem">
              <div
                className="session-timeline-dot"
                data-type={event.event_type}
                aria-hidden="true"
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  color: 'var(--lumina-text)',
                }}>
                  {eventLabels[event.event_type] ?? event.event_type}
                </div>
                <div style={{
                  fontSize: 'var(--text-xs)',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--lumina-text-muted)',
                  marginTop: '2px',
                }}>
                  {formatTime(event.timestamp)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ---- High Risk Actions Panel ----

function HighRiskActionsPanel({
  actions,
}: {
  actions: Array<{ action: string; status: string; description: string; urgency: string }>;
}) {
  if (actions.length === 0) return null;

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-4)',
      }}>
        <span
          aria-hidden="true"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-sm)',
            fontWeight: 800,
            color: 'var(--lumina-danger)',
            background: 'var(--lumina-danger-soft)',
            border: '1px solid rgba(224, 28, 43, 0.25)',
            borderRadius: 'var(--radius-md)',
            padding: '4px 10px',
          }}
        >
          03
        </span>
        <h2 style={{
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
        }}>
          High-Risk Actions
        </h2>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {actions.map((action, i) => (
          <div
            key={i}
            className="session-action-panel"
            data-urgency={action.urgency}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
              <span style={{
                fontSize: 'var(--text-sm)',
                fontWeight: 700,
                color: 'var(--lumina-text)',
              }}>
                {action.action.replace(/_/g, ' ')}
              </span>
              <span style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: action.status === 'REQUESTED' ? 'var(--lumina-warning)' : 'var(--lumina-danger)',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                border: `1px solid ${action.status === 'REQUESTED' ? 'rgba(217,164,65,0.3)' : 'rgba(224,28,43,0.3)'}`,
                background: action.status === 'REQUESTED' ? 'var(--lumina-warning-soft)' : 'var(--lumina-danger-soft)',
              }}>
                {action.status}
              </span>
            </div>
            <p style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
            }}>
              {action.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Main Component ----

export function SessionPage() {
  const session = useSessionState();
  const [submittedTypes, setSubmittedTypes] = useState<Set<string>>(new Set());

  const handleObservation = async (type: string) => {
    setSubmittedTypes((prev) => new Set([...prev, type]));
    await session.submitObservation(type);
  };

  // ---- Loading ----
  if (session.status === 'creating' || session.status === 'loading') {
    return <LoadingState message={session.status === 'creating' ? 'Creating session' : 'Loading session'} />;
  }

  // ---- Unavailable ----
  if (session.status === 'unavailable') {
    return (
      <UnavailableState
        onRetry={session.refresh}
        message={session.error ?? undefined}
      />
    );
  }

  // ---- Error (and no session data) ----
  if (session.status === 'error' && !session.session) {
    return (
      <ErrorState
        title="Session Error"
        message={session.error ?? 'An unexpected error occurred.'}
        status={session.errorCode ?? undefined}
        onRetry={() => { setSubmittedTypes(new Set()); session.refresh(); }}
      />
    );
  }

  // ---- Idle: no session → show creation view ----
  if (session.status === 'idle') {
    return (
      <SessionCreationView
        onCreate={session.startNewSession}
        error={session.error}
      />
    );
  }

  // ---- Active / Submitting session ----
  if ((session.status === 'active' || session.status === 'submitting') && session.session) {
    const decision = session.decision;

    return (
      <div className="animate-fade-in">
        {/* Status Bar */}
        <div className="session-status-bar" style={{ marginBottom: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--lumina-text-muted)' }}>CASE</span>
            <CaseID sessionId={session.session.sessionId} />
          </div>
          {decision && (
            <>
              <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
              <StatusBadge state={decision.state} size="sm" />
            </>
          )}
          <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <span style={{ color: 'var(--lumina-text-muted)' }}>EVIDENCE</span>
            <span>{session.session.evidence.length}</span>
          </span>
          {decision && (
            <>
              <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--lumina-text-muted)' }}>STATUS</span>
                <span>{decision.stateLabel}</span>
              </span>
            </>
          )}
        </div>

        {/* Decision Hero (if available) */}
        {decision && (
          <div
            className="home-status-hero"
            data-state={decision.state}
            style={{ marginBottom: 'var(--space-6)' }}
          >
            <div style={{ position: 'relative', zIndex: 1 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-4)',
                marginBottom: 'var(--space-4)',
                flexWrap: 'wrap',
              }}>
                <h1 style={{
                  fontSize: 'var(--text-2xl)',
                  fontWeight: 800,
                  letterSpacing: 'var(--tracking-tight)',
                  color: 'var(--lumina-text)',
                }}>
                  {decision.stateLabel}
                </h1>
                <StatusBadge state={decision.state} />
              </div>
              <p style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                lineHeight: 'var(--leading-relaxed)',
                maxWidth: '36rem',
                marginBottom: 'var(--space-4)',
              }}>
                {stateDescription(decision.state)}
              </p>
              {decision.reasonCodes.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {decision.reasonCodes.map((code, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-3)',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--lumina-text-secondary)',
                    }}>
                      <span aria-hidden="true" style={{
                        width: '6px', height: '6px', borderRadius: '50%',
                        background: SAFETY_STATE_COLORS[decision.state],
                      }} />
                      {code}
                    </div>
                  ))}
                </div>
              )}
              {decision.recommendedAction && (
                <Card
                  elevated
                  style={{
                    marginTop: 'var(--space-4)',
                    borderLeft: `3px solid ${SAFETY_STATE_COLORS[decision.state]}`,
                  }}
                >
                  <div style={{
                    fontSize: 'var(--text-xs)',
                    fontWeight: 700,
                    letterSpacing: 'var(--tracking-widest)',
                    textTransform: 'uppercase',
                    color: 'var(--lumina-text-muted)',
                    marginBottom: 'var(--space-2)',
                  }}>
                    Recommended Action
                  </div>
                  <p style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    color: 'var(--lumina-text)',
                    lineHeight: 'var(--leading-relaxed)',
                  }}>
                    {decision.recommendedAction}
                  </p>
                </Card>
              )}
            </div>
          </div>
        )}

        {/* Error banner (if any) */}
        {session.error && session.status === 'active' && (
          <div role="alert" style={{
            padding: 'var(--space-3) var(--space-4)',
            background: 'var(--lumina-danger-soft)',
            border: '1px solid rgba(224, 28, 43, 0.3)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-danger)',
            marginBottom: 'var(--space-6)',
          }}>
            {session.error}
          </div>
        )}

        {/* Observation Controls */}
        <ObservationControls
          onObservation={handleObservation}
          submitting={session.status === 'submitting'}
          submittedTypes={submittedTypes}
        />

        <Divider style={{ margin: 'var(--space-6) 0' }} />

        {/* High-Risk Actions */}
        {decision && decision.highRiskActions.length > 0 && (
          <>
            <HighRiskActionsPanel actions={decision.highRiskActions} />
            <Divider style={{ margin: 'var(--space-6) 0' }} />
          </>
        )}

        {/* Timeline */}
        <SessionTimeline events={session.session.events} />

        {/* End Session */}
        <div style={{ marginTop: 'var(--space-6)', display: 'flex', justifyContent: 'center' }}>
          <Button variant="ghost" onClick={session.endSession}>
            End Session
          </Button>
        </div>
      </div>
    );
  }

  // Fallback
  return (
    <ErrorState
      title="Unexpected State"
      message="The session screen encountered an unexpected state."
      onRetry={session.refresh}
    />
  );
}
