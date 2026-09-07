/* ============================================================
   LUMINA Incident History
   ============================================================
   A real, chronological list of past incidents loaded from the
   backend incident listing endpoint. Every entry is a real
   record — never fabricated data.
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { useIncidentList } from '@/hooks/useIncidentList';
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_PRIORITY_LABELS,
} from '@/hooks/useIncidentState';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { EmptyState } from '@/components/EmptyState';
import type { IncidentStatus, RecoverySnapshot } from '@/types/incident';

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

export function HistoryPage() {
  const navigate = useNavigate();
  const { status, incidents, error, errorCode, refresh } = useIncidentList();

  if (status === 'loading') {
    return <LoadingState message="Loading your history…" />;
  }

  if (status === 'unavailable') {
    return <UnavailableState message={error ?? undefined} onRetry={refresh} />;
  }

  if (status === 'error') {
    return (
      <ErrorState
        title="Could not load your history"
        message={error ?? 'Something went wrong.'}
        status={errorCode ?? undefined}
        onRetry={refresh}
      />
    );
  }

  if (status === 'unauthorized') {
    return (
      <div className="animate-fade-in">
        <SectionHeader
          title="Incident History"
          subtitle="A private record of what LUMINA has helped with"
        />
        <Card>
          <EmptyState
            title="Incident history isn't available here"
            description="LUMINA only shows incident history on the device that created it."
          />
        </Card>
      </div>
    );
  }

  if (incidents.length === 0) {
    return (
      <div className="animate-fade-in">
        <SectionHeader
          title="Incident History"
          subtitle="A private record of what LUMINA has helped with"
        />
        <Card>
          <EmptyState
            title="No incidents yet"
            description="When you start an incident, it will appear here with its status and the next step to stay safe."
            action={
              <Button variant="primary" onClick={() => navigate('/incident/new')}>
                Start an Incident
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <SectionHeader
        title="Incident History"
        subtitle="A private record of what LUMINA has helped with"
      />

      <ul
        style={{
          listStyle: 'none',
          padding: 0,
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-3)',
          marginBottom: 'var(--space-6)',
        }}
      >
        {incidents.map((incident) => {
          const statusLabel = INCIDENT_STATUS_LABELS[incident.status];
          return (
            <li key={incident.incident_id}>
              <button
                type="button"
                onClick={() => navigate(`/incident?id=${encodeURIComponent(incident.incident_id)}`)}
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

      <Button variant="secondary" onClick={() => navigate('/incident/new')}>
        Start a new incident
      </Button>
    </div>
  );
}