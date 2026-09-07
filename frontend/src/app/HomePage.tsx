/* ============================================================
   LUMINA Home Page (Front Door)
   ============================================================
   The primary product doorway: a calm, clear entry into the
   Incident experience. Shows the current incident (if any) and
   private recent history from the real incident list endpoint.
   No fake data.
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { useHomeState } from '@/hooks/useHomeState';
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_PRIORITY_LABELS,
} from '@/hooks/useIncidentState';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { EmptyState } from '@/components/EmptyState';
import type { Incident, IncidentStatus, IncidentSummary, RecoverySnapshot } from '@/types/incident';

// Backend-derived recovery continuity note (CP-30). Null unless the incident
// reached AFTER_DAMAGE, so pre-damage preventive incidents stay quiet.
function recoveryNote(metadata?: Record<string, unknown>): string | null {
  if (!metadata) return null;
  const recovery = metadata.recovery as RecoverySnapshot | undefined;
  if (recovery && recovery.phase === 'AFTER_DAMAGE' && recovery.short_description) {
    return recovery.short_description;
  }
  return null;
}

const STATUS_COLORS: Record<IncidentStatus, string> = {
  ACTIVE: 'var(--lumina-system)',
  MONITORING: 'var(--lumina-warning)',
  ACTION_REQUIRED: 'var(--lumina-danger)',
  RECOVERING: 'var(--lumina-investigation)',
  CLOSED: 'var(--lumina-recovery)',
  UNKNOWN: 'var(--lumina-text-muted)',
};

function formatDate(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

// ---- Front door hero ----

function FrontDoorHero({
  onStart,
  hasActiveIncident,
}: {
  onStart: () => void;
  hasActiveIncident: boolean;
}) {
  return (
    <section aria-label="Start an incident" className="home-no-session-hero">
      {!hasActiveIncident && (
        <div
          role="status"
          aria-label="Current status: no active incident — all clear"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            position: 'relative',
            zIndex: 1,
            padding: 'var(--space-1) var(--space-3)',
            borderRadius: 'var(--radius-full)',
            background: 'rgba(90, 184, 122, 0.1)',
            border: '1px solid rgba(90, 184, 122, 0.25)',
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            color: 'var(--lumina-recovery)',
            marginBottom: 'var(--space-5)',
          }}
        >
          <span aria-hidden="true">◉</span>
          All Clear
        </div>
      )}

      <h1
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: 'var(--text-3xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-3)',
        }}
      >
        Something happened?
      </h1>

      <p
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: 'var(--text-base)',
          color: 'var(--lumina-text-secondary)',
          maxWidth: '28rem',
          margin: '0 auto',
          marginBottom: 'var(--space-6)',
          lineHeight: 'var(--leading-relaxed)',
        }}
      >
        Let's figure out what to do next. Start an incident when something
        suspicious happens — a call, a message, or a conversation that doesn't
        feel right.
      </p>

      <div style={{ position: 'relative', zIndex: 1 }}>
        <Button variant="primary" size="lg" onClick={onStart}>
          Start an Incident
        </Button>
      </div>

      <p
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: 'var(--text-xs)',
          color: 'var(--lumina-text-muted)',
          maxWidth: '24rem',
          margin: 'var(--space-4) auto 0',
          lineHeight: 'var(--leading-relaxed)',
        }}
      >
        LUMINA never records your calls without asking. You choose what to
        share — a live recording, an existing audio file, or a transcript you
        type or paste.
      </p>
    </section>
  );
}

// ---- Active incident card ----

function ActiveIncidentCard({
  incident,
  onOpen,
}: {
  incident: Incident;
  onOpen: () => void;
}) {
  const statusLabel = INCIDENT_STATUS_LABELS[incident.status];
  return (
    <Card
      elevated
      glow
      style={{
        borderLeft: `3px solid ${STATUS_COLORS[incident.status]}`,
        background: 'var(--lumina-surface-elevated)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div>
          <div
            role="status"
            aria-label={`Active incident status: ${statusLabel}`}
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: STATUS_COLORS[incident.status],
              marginBottom: '2px',
            }}
          >
            {statusLabel}
          </div>
          <div
            style={{
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              color: 'var(--lumina-text)',
            }}
          >
            Active Incident
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={onOpen}>
          Open Incident
        </Button>
      </div>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
          marginTop: 'var(--space-3)',
        }}
      >
        {incident.next_action?.action ?? 'Waiting for more details.'}
      </p>
      {recoveryNote(incident.metadata) && (
        <div
          role="status"
          aria-label="Recovery record"
          style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--lumina-text-muted)',
            lineHeight: 'var(--leading-relaxed)',
            marginTop: 'var(--space-2)',
          }}
        >
          {recoveryNote(incident.metadata)}
        </div>
      )}
    </Card>
  );
}

// ---- Recent incidents ----

function RecentIncidents({
  incidents,
  status,
  onRetry,
  onOpen,
  onStart,
}: {
  incidents: IncidentSummary[];
  status: string;
  onRetry: () => void;
  onOpen: (incidentId: string) => void;
  onStart: () => void;
}) {
  return (
    <section aria-label="Recent incidents">
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <h2
          style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 700,
            color: 'var(--lumina-text)',
            marginBottom: '2px',
          }}
        >
          Recent Incidents
        </h2>
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
          }}
        >
          A private record of what LUMINA has helped with.
        </p>
      </div>

      {status === 'loading' && (
        <LoadingState message="Loading your recent incidents…" />
      )}

      {status === 'unauthorized' && (
        <Card>
          <EmptyState
            title="Incident history isn't available here"
            description="LUMINA only shows incident history on the device that created it. Moments shared on this device may still be in progress."
          />
        </Card>
      )}

      {(status === 'error' || status === 'unavailable') && (
        <Card>
          <div role="alert" style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
            <p
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                lineHeight: 'var(--leading-relaxed)',
                marginBottom: 'var(--space-4)',
              }}
            >
              Couldn't load your recent incidents right now.
            </p>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Try Again
            </Button>
          </div>
        </Card>
      )}

      {status === 'ready' && incidents.length === 0 && (
        <Card>
          <EmptyState
            title="No incidents yet"
            description="When you start an incident, it will appear here. You can also open past incidents from History."
            action={
              <Button variant="primary" onClick={onStart}>
                Start an Incident
              </Button>
            }
          />
        </Card>
      )}

      {status === 'ready' && incidents.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {incidents.slice(0, 5).map((incident) => {
            const statusLabel = INCIDENT_STATUS_LABELS[incident.status];
            return (
              <li key={incident.incident_id}>
                <button
                  type="button"
                  onClick={() => onOpen(incident.incident_id)}
                  aria-label={`Incident ${incident.incident_id}, ${statusLabel}, ${formatDate(incident.created_at)}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-3)',
                    width: '100%',
                    textAlign: 'left',
                    background: 'var(--lumina-surface)',
                    border: '1px solid var(--lumina-border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: 'var(--space-4)',
                    cursor: 'pointer',
                    color: 'var(--lumina-text)',
                    transition: 'border-color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out)',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.background = 'var(--lumina-surface-hover)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'var(--lumina-border-strong)';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.background = 'var(--lumina-surface)';
                    (e.currentTarget as HTMLElement).style.borderColor = 'var(--lumina-border)';
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: STATUS_COLORS[incident.status],
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flex: 1 }}>
                    <span
                      style={{
                        display: 'block',
                        fontSize: 'var(--text-sm)',
                        fontWeight: 700,
                        color: 'var(--lumina-text)',
                      }}
                    >
                      {statusLabel}
                    </span>
                    <span
                      style={{
                        display: 'block',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--lumina-text-muted)',
                        marginTop: '2px',
                      }}
                    >
                      {formatDate(incident.created_at)} · {INCIDENT_PRIORITY_LABELS[incident.priority]}
                    </span>
                    {recoveryNote(incident.metadata) && (
                      <span
                        style={{
                          display: 'block',
                          fontSize: 'var(--text-xs)',
                          color: 'var(--lumina-text-muted)',
                          marginTop: '2px',
                        }}
                      >
                        {recoveryNote(incident.metadata)}
                      </span>
                    )}
                  </span>
                  <span
                    aria-hidden="true"
                    style={{
                      color: 'var(--lumina-text-muted)',
                      fontSize: 'var(--text-lg)',
                    }}
                  >
                    ›
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

// ---- Main component ----

export function HomePage() {
  const navigate = useNavigate();
  const {
    status,
    incidents,
    incidentsStatus,
    activeIncident,
    error,
    errorCode,
    refresh,
  } = useHomeState();

  if (status === 'loading') {
    return <LoadingState message="Connecting to LUMINA" />;
  }

  if (status === 'error') {
    return (
      <ErrorState
        title="Connection Error"
        message={error ?? 'Could not connect to LUMINA right now.'}
        status={errorCode ?? undefined}
        onRetry={refresh}
      />
    );
  }

  if (status === 'unavailable') {
    return <UnavailableState message={error ?? undefined} onRetry={refresh} />;
  }

  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-6)',
      }}
    >
      <FrontDoorHero
        onStart={() => navigate('/incident/new')}
        hasActiveIncident={!!activeIncident}
      />

      {activeIncident && (
        <ActiveIncidentCard
          incident={activeIncident}
          onOpen={() => navigate('/incident')}
        />
      )}

      <RecentIncidents
        incidents={incidents}
        status={incidentsStatus}
        onRetry={refresh}
        onOpen={(id) => navigate(`/incident?id=${encodeURIComponent(id)}`)}
        onStart={() => navigate('/incident/new')}
      />
    </div>
  );
}