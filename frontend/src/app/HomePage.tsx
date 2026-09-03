/* ============================================================
   LUMINA Home Screen
   ============================================================
   The real Home experience. Communicates:
   - What is happening right now?
   - Is there an active safety situation?
   - What evidence/status is currently known?
   - What can the user do next?

   Uses real backend data only. No fake data.
   ============================================================ */

import { useHomeState } from '@/hooks/useHomeState';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { CaseID } from '@/components/CaseID';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { Divider } from '@/components/Divider';
import type { SafetyState } from '@/types/safety';
import { SAFETY_STATE_LABELS } from '@/types/safety';

// ---- Helpers ----

function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function stateDescription(state: SafetyState): string {
  switch (state) {
    case 'CLEAR':
      return 'No safety concerns detected. The situation appears normal.';
    case 'WATCH':
      return 'Observations have been recorded. Stay alert for requests for money, codes, or access.';
    case 'VERIFY':
      return 'A high-risk action has been requested. Verify the caller independently before proceeding.';
    case 'PAUSE':
      return 'An irreversible action has been requested. Do not share codes, passwords, or send money.';
    case 'PROTECT':
      return 'Coercion and secrecy detected. Stop and verify independently. Do not send money, codes, or grant access.';
    case 'RECOVERY':
      return 'A high-risk action may have been performed. Secure your accounts and contact officials directly.';
  }
}

function stateIcon(state: SafetyState): string {
  switch (state) {
    case 'CLEAR': return '●';
    case 'WATCH': return '◉';
    case 'VERIFY': return '◈';
    case 'PAUSE': return '◥';
    case 'PROTECT': return '◆';
    case 'RECOVERY': return '◎';
  }
}



// ---- Sub-components ----

function NoSessionHero() {
  return (
    <div className="home-no-session-hero">
      {/* Atmospheric grid overlay — no content, purely visual */}
      <div aria-hidden="true" style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        background: 'radial-gradient(500px 250px at 50% 0%, rgba(90, 184, 122, 0.04), transparent 60%)',
      }} />

      <div style={{ position: 'relative', zIndex: 1 }}>
        {/* Status indicator */}
        <div
          role="status"
          aria-label="Current safety status: Clear — no active session"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            padding: 'var(--space-3) var(--space-5)',
            background: 'var(--lumina-recovery-soft)',
            border: '1px solid rgba(90, 184, 122, 0.25)',
            borderRadius: 'var(--radius-full)',
            marginBottom: 'var(--space-6)',
          }}
        >
          <span aria-hidden="true" style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: 'var(--lumina-recovery)',
          }} />
          <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            color: 'var(--lumina-recovery)',
          }}>
            All Clear
          </span>
        </div>

        {/* Primary message */}
        <h1 style={{
          fontSize: 'var(--text-3xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-tight)',
          color: 'var(--lumina-text)',
          lineHeight: 'var(--leading-tight)',
          marginBottom: 'var(--space-4)',
        }}>
          Nothing requires your attention right now.
        </h1>

        {/* Subtitle */}
        <p style={{
          fontSize: 'var(--text-base)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
          maxWidth: '32rem',
          margin: '0 auto',
        }}>
          When a call begins, LUMINA will collect evidence and provide
          safety guidance based on what is actually observed.
        </p>
      </div>
    </div>
  );
}

function ActiveSessionHero({
  state,
  stateLabel,
  reasonCodes,
  recommendedAction,
  evidenceCount,
  observations,
  hasRequestedHighRiskAction,
  hasPerformedHighRiskAction,
}: {
  state: SafetyState;
  stateLabel: string;
  reasonCodes: string[];
  recommendedAction: string;
  evidenceCount: number;
  observations: string[];
  hasRequestedHighRiskAction: boolean;
  hasPerformedHighRiskAction: boolean;
}) {
  return (
    <div className="home-status-hero" data-state={state}>
      <div style={{ position: 'relative', zIndex: 1 }}>
        {/* Eyebrow: Forensic metadata */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-4)',
          marginBottom: 'var(--space-5)',
          flexWrap: 'wrap',
        }}>
          <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text-muted)',
          }}>
            Safety Assessment
          </span>
          <span style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--lumina-border-strong)',
          }}>
            •
          </span>
          <span style={{
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            color: 'var(--lumina-text-muted)',
            letterSpacing: 'var(--tracking-wide)',
          }}>
            {evidenceCount} evidence {evidenceCount === 1 ? 'piece' : 'pieces'}
          </span>
          {observations.length > 0 && (
            <>
              <span style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--lumina-border-strong)',
              }}>
                •
              </span>
              <span style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--lumina-text-muted)',
                letterSpacing: 'var(--tracking-wide)',
              }}>
                {observations.length} observation{observations.length !== 1 ? 's' : ''}
              </span>
            </>
          )}
        </div>

        {/* Primary status */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-4)',
          marginBottom: 'var(--space-5)',
          flexWrap: 'wrap',
        }}>
          <span aria-hidden="true" style={{
            fontSize: 'var(--text-4xl)',
            lineHeight: 1,
            opacity: 0.6,
          }}>
            {stateIcon(state)}
          </span>
          <div>
            <h1 style={{
              fontSize: 'var(--text-3xl)',
              fontWeight: 800,
              letterSpacing: 'var(--tracking-tight)',
              color: 'var(--lumina-text)',
              lineHeight: 'var(--leading-tight)',
              marginBottom: 'var(--space-1)',
            }}>
              {stateLabel}
            </h1>
            <StatusBadge state={state} size="sm" />
          </div>
        </div>

        {/* Description */}
        <p style={{
          fontSize: 'var(--text-base)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
          maxWidth: '36rem',
          marginBottom: 'var(--space-6)',
        }}>
          {stateDescription(state)}
        </p>

        {/* Reason codes */}
        {reasonCodes.length > 0 && (
          <div className="home-reason-list" style={{ marginBottom: 'var(--space-6)' }}>
            {reasonCodes.map((code, i) => (
              <div key={i} className="home-reason-item">
                <span
                  className="home-reason-dot"
                  aria-hidden="true"
                  style={{ background: SAFETY_STATE_COLORS[state] }}
                />
                <span>{code}</span>
              </div>
            ))}
          </div>
        )}

        {/* Recommended action */}
        {recommendedAction && (
          <Card
            elevated
            style={{
              borderLeft: `3px solid ${SAFETY_STATE_COLORS[state]}`,
              animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) 150ms both',
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
              {recommendedAction}
            </p>
          </Card>
        )}

        {/* High-risk action indicators */}
        {(hasRequestedHighRiskAction || hasPerformedHighRiskAction) && (
          <div style={{
            display: 'flex',
            gap: 'var(--space-3)',
            marginTop: 'var(--space-4)',
            flexWrap: 'wrap',
          }}>
            {hasRequestedHighRiskAction && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--lumina-warning-soft)',
                border: '1px solid rgba(217, 164, 65, 0.3)',
                borderRadius: 'var(--radius-full)',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: 'var(--lumina-warning)',
              }}>
                <span aria-hidden="true">▲</span>
                Action Requested
              </span>
            )}
            {hasPerformedHighRiskAction && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--lumina-danger-soft)',
                border: '1px solid rgba(224, 28, 43, 0.3)',
                borderRadius: 'var(--radius-full)',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: 'var(--lumina-danger)',
              }}>
                <span aria-hidden="true">◆</span>
                Action Performed
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SessionContext({ session, decision }: {
  session: { sessionId: string; startedAt: string; eventCount: number; evidenceCount: number };
  decision: { state: SafetyState; missingInformation: string[]; observations: string[] } | null;
}) {
  return (
    <Card elevated style={{ animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) 200ms both' }}>
      {/* Forensic metadata bar */}
      <div className="home-forensic-bar" style={{ marginBottom: 'var(--space-4)' }}>
        <div className="home-forensic-item">
          <span style={{ color: 'var(--lumina-text-muted)' }}>CASE</span>
          <CaseID sessionId={session.sessionId} />
        </div>
        <span className="home-forensic-separator" aria-hidden="true">|</span>
        <div className="home-forensic-item">
          <span style={{ color: 'var(--lumina-text-muted)' }}>OPENED</span>
          <span>{formatTimestamp(session.startedAt)}</span>
        </div>
        <span className="home-forensic-separator" aria-hidden="true">|</span>
        <div className="home-forensic-item">
          <span style={{ color: 'var(--lumina-text-muted)' }}>EVENTS</span>
          <span>{session.eventCount}</span>
        </div>
      </div>

      {/* Context rows */}
      <div>
        <div className="home-context-row">
          <span className="home-context-label">Status</span>
          <span className="home-context-value">
            {decision ? SAFETY_STATE_LABELS[decision.state] : 'Decision pending'}
          </span>
        </div>
        <div className="home-context-row">
          <span className="home-context-label">Evidence</span>
          <span className="home-context-value">
            {session.evidenceCount} piece{session.evidenceCount !== 1 ? 's' : ''} collected
          </span>
        </div>
        {decision && decision.observations.length > 0 && (
          <div className="home-context-row">
            <span className="home-context-label">Observations</span>
            <span className="home-context-value">
              {decision.observations.length} user-reported
            </span>
          </div>
        )}
        {decision && decision.missingInformation.length > 0 && (
          <div className="home-context-row">
            <span className="home-context-label">Unknown</span>
            <span className="home-context-value" style={{ color: 'var(--lumina-text-muted)' }}>
              {decision.missingInformation.length} item{decision.missingInformation.length !== 1 ? 's' : ''} not yet available
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

function RecentActivitySection() {
  return (
    <div style={{ animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) 300ms both' }}>
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-5)',
        paddingBottom: 'var(--space-4)',
        borderBottom: '1px solid var(--lumina-border-subtle)',
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
            flexShrink: 0,
          }}
        >
          02
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            lineHeight: 'var(--leading-tight)',
            color: 'var(--lumina-text)',
          }}>
            Recent Activity
          </h2>
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            marginTop: 'var(--space-1)',
            lineHeight: 'var(--leading-relaxed)',
          }}>
            Session history from the connected backend
          </p>
        </div>
      </div>

      <Card>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: 'var(--space-8) var(--space-4)',
          textAlign: 'center',
        }}>
          <div
            aria-hidden="true"
            style={{
              width: '2.5rem',
              height: '2.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 'var(--radius-lg)',
              background: 'var(--lumina-surface-elevated)',
              border: '1px solid var(--lumina-border)',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-4)',
              fontSize: 'var(--text-lg)',
            }}
          >
            ◌
          </div>
          <h3 style={{
            fontSize: 'var(--text-base)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-2)',
          }}>
            Session History Unavailable
          </h3>
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            maxWidth: '24rem',
            lineHeight: 'var(--leading-relaxed)',
          }}>
            The connected backend does not currently expose a session listing endpoint.
            Session history will be available when that endpoint is implemented.
          </p>
        </div>
      </Card>
    </div>
  );
}

// ---- SAFETY_STATE_COLORS (local reference for inline use) ----
const SAFETY_STATE_COLORS: Record<SafetyState, string> = {
  CLEAR: 'var(--lumina-recovery)',
  WATCH: 'var(--lumina-warning)',
  PAUSE: 'var(--lumina-danger)',
  VERIFY: 'var(--lumina-warning)',
  PROTECT: 'var(--lumina-danger)',
  RECOVERY: 'var(--lumina-investigation)',
};

// ---- Main Component ----

export function HomePage() {
  const homeState = useHomeState();

  // ---- Loading ----
  if (homeState.status === 'loading') {
    return (
      <div>
        <LoadingState message="Connecting to LUMINA" />
      </div>
    );
  }

  // ---- Unavailable ----
  if (homeState.status === 'unavailable') {
    return (
      <UnavailableState
        onRetry={homeState.refresh}
        message={
          homeState.error
            ? `Unable to connect to the LUMINA backend: ${homeState.error}`
            : undefined
        }
      />
    );
  }

  // ---- Error ----
  if (homeState.status === 'error') {
    return (
      <ErrorState
        title="Connection Error"
        message={homeState.error ?? 'An unexpected error occurred.'}
        status={homeState.errorCode ?? undefined}
        onRetry={homeState.refresh}
      />
    );
  }

  // ---- No Active Session ----
  if (homeState.status === 'no_session') {
    return (
      <div>
        <NoSessionHero />

        <Divider style={{ margin: 'var(--space-6) 0' }} />

        <RecentActivitySection />
      </div>
    );
  }

  // ---- Active Session ----
  if (homeState.status === 'active_session' && homeState.session) {
    return (
      <div>
        {/* Primary Status Hero */}
        {homeState.decision ? (
          <ActiveSessionHero
            state={homeState.decision.state}
            stateLabel={homeState.decision.stateLabel}
            reasonCodes={homeState.decision.reasonCodes}
            recommendedAction={homeState.decision.recommendedAction}
            evidenceCount={homeState.decision.evidenceCount}
            observations={homeState.decision.observations}
            hasRequestedHighRiskAction={homeState.decision.hasRequestedHighRiskAction}
            hasPerformedHighRiskAction={homeState.decision.hasPerformedHighRiskAction}
          />
        ) : (
          /* Session exists but decision unavailable */
          <Card elevated style={{
            marginBottom: 'var(--space-6)',
            borderLeft: '3px solid var(--lumina-warning)',
          }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-warning)',
              marginBottom: 'var(--space-2)',
            }}>
              Decision Unavailable
            </div>
            <p style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
            }}>
              {homeState.error ?? 'The safety decision could not be retrieved. The session is active but the assessment is pending.'}
            </p>
          </Card>
        )}

        {/* Session Context */}
        <SessionContext
          session={homeState.session}
          decision={homeState.decision}
        />

        <Divider style={{ margin: 'var(--space-6) 0' }} />

        {/* Recent Activity */}
        <RecentActivitySection />
      </div>
    );
  }

  // Fallback (should not reach here)
  return (
    <ErrorState
      title="Unexpected State"
      message="The home screen encountered an unexpected state."
      onRetry={homeState.refresh}
    />
  );
}
