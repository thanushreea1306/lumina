/* ============================================================
   LUMINA Evidence Board
   ============================================================
   The real Evidence experience. Implements:
   - Evidence display from real session data
   - Evidence detail panel
   - Timeline view
   - Status/source visual treatment
   - No-evidence state
   - Unavailable state
   ============================================================ */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useSessionState } from '@/hooks/useSessionState';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { CaseID } from '@/components/CaseID';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { EmptyState } from '@/components/EmptyState';
import {
  EVIDENCE_STATUS_LABELS,
  EVIDENCE_SOURCE_LABELS,
} from '@/types/safety';
import type { SafetyState, EvidenceStatus, EvidenceSource } from '@/types/safety';

// ---- Helpers ----

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function statusColor(status: string): string {
  switch (status as EvidenceStatus) {
    case 'OBSERVED': return 'var(--lumina-system)';
    case 'USER_CONFIRMED': return 'var(--lumina-recovery)';
    case 'UNKNOWN': return 'var(--lumina-text-muted)';
    case 'NOT_AVAILABLE': return 'var(--lumina-text-muted)';
    case 'NOT_PERMITTED': return 'var(--lumina-warning)';
    case 'INFERRED': return 'var(--lumina-investigation)';
    default: return 'var(--lumina-text-muted)';
  }
}

function sourceIcon(source: string): string {
  switch (source as EvidenceSource) {
    case 'DEVICE': return '📱';
    case 'USER': return '👤';
    case 'SYSTEM': return '⚙';
    case 'MODEL': return '🧠';
    case 'RULE': return '📏';
    default: return '•';
  }
}

function evidenceTypeLabel(type: string): string {
  return type
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---- Evidence Detail Panel ----

function EvidenceDetailPanel({
  evidence,
  onClose,
}: {
  evidence: {
    evidence_id: string;
    type: string;
    value: unknown;
    status: string;
    source: string;
    timestamp: string;
    sequence: number;
    confidence: number | null;
    metadata: Record<string, unknown>;
    session_id: string;
  };
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    if (panel) {
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length > 0) {
        focusables[0].focus();
      } else {
        panel.focus();
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previouslyFocused && previouslyFocused.focus) {
        previouslyFocused.focus();
      }
    };
  }, [onClose]);

  return (
    <>
      <div
        className="evidence-detail-backdrop"
        onClick={onClose}
        role="button"
        tabIndex={-1}
        aria-label="Close detail panel"
      />
      <div
        ref={panelRef}
        className="evidence-detail-panel"
        role="dialog"
        aria-label={`Evidence detail: ${evidence.type}`}
        aria-modal="true"
        tabIndex={-1}
      >
        <div style={{
          padding: 'var(--space-5) var(--space-6)',
          borderBottom: '1px solid var(--lumina-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          background: 'var(--lumina-surface-elevated)',
          zIndex: 1,
        }}>
          <h2 style={{
            fontSize: 'var(--text-lg)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
          }}>
            Evidence Detail
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none',
              border: '1px solid var(--lumina-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--lumina-text-secondary)',
              cursor: 'pointer',
              padding: 'var(--space-2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '2rem',
              height: '2rem',
            }}
          >
            ✕
          </button>
        </div>
        <div style={{ padding: 'var(--space-6)' }}>
          <div style={{ marginBottom: 'var(--space-6)' }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-2)',
            }}>
              Type
            </div>
            <div style={{
              fontSize: 'var(--text-lg)',
              fontWeight: 700,
              color: 'var(--lumina-text)',
            }}>
              {evidenceTypeLabel(evidence.type)}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-6)', flexWrap: 'wrap' }}>
            <span
              className="evidence-status-badge"
              style={{
                color: statusColor(evidence.status),
                borderColor: statusColor(evidence.status),
                background: `${statusColor(evidence.status)}18`,
              }}
            >
              <span aria-hidden="true" style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor' }} />
              {EVIDENCE_STATUS_LABELS[evidence.status as EvidenceStatus] ?? evidence.status}
            </span>
            <span className="evidence-source-badge">
              <span aria-hidden="true">{sourceIcon(evidence.source)}</span>
              {EVIDENCE_SOURCE_LABELS[evidence.source as EvidenceSource] ?? evidence.source}
            </span>
          </div>
          <Card>
            <div className="evidence-meta-row">
              <span className="evidence-meta-label">Evidence ID</span>
              <span className="evidence-meta-value" style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
                {evidence.evidence_id}
              </span>
            </div>
            <div className="evidence-meta-row">
              <span className="evidence-meta-label">Session</span>
              <CaseID sessionId={evidence.session_id} />
            </div>
            <div className="evidence-meta-row">
              <span className="evidence-meta-label">Timestamp</span>
              <span className="evidence-meta-value">{formatTimestamp(evidence.timestamp)}</span>
            </div>
            <div className="evidence-meta-row">
              <span className="evidence-meta-label">Sequence</span>
              <span className="evidence-meta-value">{evidence.sequence}</span>
            </div>
            {evidence.confidence !== null && (
              <div className="evidence-meta-row">
                <span className="evidence-meta-label">Confidence</span>
                <span className="evidence-meta-value">{evidence.confidence}</span>
              </div>
            )}
            {evidence.value !== null && evidence.value !== undefined && (
              <div className="evidence-meta-row">
                <span className="evidence-meta-label">Value</span>
                <span className="evidence-meta-value">
                  {typeof evidence.value === 'object'
                    ? JSON.stringify(evidence.value)
                    : String(evidence.value)}
                </span>
              </div>
            )}
            {Object.keys(evidence.metadata).length > 0 && (
              <div className="evidence-meta-row">
                <span className="evidence-meta-label">Metadata</span>
                <span className="evidence-meta-value" style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)' }}>
                  {JSON.stringify(evidence.metadata, null, 2)}
                </span>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

// ---- Evidence Card ----

function EvidenceCard({
  evidence,
  index,
  onClick,
}: {
  evidence: {
    evidence_id: string;
    type: string;
    value: unknown;
    status: string;
    source: string;
    timestamp: string;
    sequence: number;
    confidence: number | null;
    metadata: Record<string, unknown>;
  };
  index: number;
  onClick: () => void;
}) {
  return (
    <button
      className="evidence-card"
      role="button"
      onClick={onClick}
      aria-label={`Evidence: ${evidenceTypeLabel(evidence.type)}, status: ${evidence.status}`}
      style={{ animationDelay: `${index * 50}ms`, textAlign: 'left' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
        <span className="evidence-number">{String(evidence.sequence + 1).padStart(2, '0')}</span>
        <span
          className="evidence-status-badge"
          style={{
            color: statusColor(evidence.status),
            borderColor: statusColor(evidence.status),
            background: `${statusColor(evidence.status)}18`,
          }}
        >
          <span aria-hidden="true" style={{ width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor' }} />
          {EVIDENCE_STATUS_LABELS[evidence.status as EvidenceStatus] ?? evidence.status}
        </span>
      </div>
      <div style={{
        fontSize: 'var(--text-sm)',
        fontWeight: 700,
        color: 'var(--lumina-text)',
        marginBottom: 'var(--space-2)',
      }}>
        {evidenceTypeLabel(evidence.type)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
        <span className="evidence-source-badge">
          <span aria-hidden="true">{sourceIcon(evidence.source)}</span>
          {EVIDENCE_SOURCE_LABELS[evidence.source as EvidenceSource] ?? evidence.source}
        </span>
        <span style={{
          fontSize: 'var(--text-xs)',
          fontFamily: 'var(--font-mono)',
          color: 'var(--lumina-text-muted)',
        }}>
          {formatTimestamp(evidence.timestamp)}
        </span>
      </div>
      {evidence.value !== null && evidence.value !== undefined && (
        <div style={{
          marginTop: 'var(--space-3)',
          padding: 'var(--space-2) var(--space-3)',
          background: 'rgba(0,0,0,0.2)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-xs)',
          fontFamily: 'var(--font-mono)',
          color: 'var(--lumina-text-muted)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {typeof evidence.value === 'object'
            ? JSON.stringify(evidence.value)
            : String(evidence.value)}
        </div>
      )}
    </button>
  );
}

// ---- No Session State ----

function NoSessionEvidenceView() {
  return (
    <div className="animate-fade-in">
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-6)',
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
          04
        </span>
        <div>
          <h1 style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
          }}>
            Evidence Board
          </h1>
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            marginTop: 'var(--space-1)',
          }}>
            Review collected evidence and safety decisions
          </p>
        </div>
      </div>
      <EmptyState
        title="No Active Session"
        description="Start a session from the Session screen to begin collecting evidence. Each piece of evidence is typed, timestamped, and attributed to its source."
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        }
      />
    </div>
  );
}

// ---- Main Component ----

export function EvidencePage() {
  const { session, decision, status, refresh } = useSessionState();
  const [selectedEvidence, setSelectedEvidence] = useState<number | null>(null);

  const handleCloseDetail = useCallback(() => setSelectedEvidence(null), []);

  // ---- Loading ----
  if (status === 'loading' || status === 'creating') {
    return <LoadingState message="Loading evidence" />;
  }

  // ---- Unavailable ----
  if (status === 'unavailable') {
    return (
      <UnavailableState
        onRetry={refresh}
        message="Unable to load evidence data from the LUMINA backend."
      />
    );
  }

  // ---- Error ----
  if (status === 'error' && !session) {
    return (
      <ErrorState
        title="Evidence Unavailable"
        message="Could not load evidence data."
        onRetry={refresh}
      />
    );
  }

  // ---- No session (idle or no session data) ----
  if (status === 'idle' || !session) {
    return <NoSessionEvidenceView />;
  }

  // ---- Active session with evidence ----
  const evidenceList = session.evidence;
  const hasEvidence = evidenceList.length > 0;

  // Group by source
  const grouped = evidenceList.reduce((acc, ev) => {
    const src = ev.source;
    if (!acc[src]) acc[src] = [];
    acc[src].push(ev);
    return acc;
  }, {} as Record<string, typeof evidenceList>);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
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
          04
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
          }}>
            Evidence Board
          </h1>
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            marginTop: 'var(--space-1)',
          }}>
            {hasEvidence
              ? `${evidenceList.length} piece${evidenceList.length !== 1 ? 's' : ''} of evidence collected`
              : 'No evidence recorded yet'}
          </p>
        </div>
        {decision && (
          <StatusBadge state={decision.state as SafetyState} size="sm" />
        )}
      </div>

      {/* Forensic metadata bar */}
      <div className="session-status-bar" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ color: 'var(--lumina-text-muted)' }}>CASE</span>
          <CaseID sessionId={session.sessionId} />
        </div>
        <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ color: 'var(--lumina-text-muted)' }}>EVIDENCE</span>
          <span>{evidenceList.length}</span>
        </span>
        {decision && (
          <>
            <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
            <StatusBadge state={decision.state as SafetyState} size="sm" />
          </>
        )}
      </div>

      {/* No evidence yet */}
      {!hasEvidence && (
        <Card>
          <EmptyState
            title="No Evidence Recorded"
            description="Evidence will appear here as observations are submitted and device events are captured during the session."
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            }
          />
        </Card>
      )}

      {/* Evidence by source groups */}
      {hasEvidence && Object.entries(grouped).map(([source, items]) => (
        <div key={source} style={{ marginBottom: 'var(--space-6)' }}>
          <div
            className="evidence-group-header"
            style={{ color: source === 'USER' ? 'var(--lumina-recovery)' : 'var(--lumina-system)' }}
          >
            {sourceIcon(source)} {EVIDENCE_SOURCE_LABELS[source as EvidenceSource] ?? source} — {items.length} item{items.length !== 1 ? 's' : ''}
          </div>
          <div className="evidence-grid">
            {items.map((ev, i) => (
              <EvidenceCard
                key={ev.evidence_id}
                evidence={ev}
                index={i}
                onClick={() => {
                  const globalIndex = evidenceList.findIndex((e) => e.evidence_id === ev.evidence_id);
                  setSelectedEvidence(globalIndex);
                }}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Timeline view */}
      {hasEvidence && (
        <div style={{ marginTop: 'var(--space-8)' }}>
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
              05
            </span>
            <h2 style={{
              fontSize: 'var(--text-lg)',
              fontWeight: 800,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text)',
            }}>
              Evidence Timeline
            </h2>
          </div>
          <Card>
            <div className="evidence-timeline" role="list" aria-label="Evidence timeline">
              {evidenceList.map((ev) => (
                <div key={ev.evidence_id} className="evidence-timeline-item" role="listitem">
                  <div
                    className="evidence-timeline-dot"
                    style={{ background: statusColor(ev.status) }}
                    aria-hidden="true"
                  />
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-3)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span style={{
                        fontSize: 'var(--text-sm)',
                        fontWeight: 600,
                        color: 'var(--lumina-text)',
                      }}>
                        {evidenceTypeLabel(ev.type)}
                      </span>
                      <span style={{
                        fontSize: 'var(--text-xs)',
                        color: 'var(--lumina-text-muted)',
                        marginLeft: 'var(--space-3)',
                      }}>
                        {EVIDENCE_SOURCE_LABELS[ev.source as EvidenceSource] ?? ev.source}
                      </span>
                    </div>
                    <span style={{
                      fontSize: 'var(--text-xs)',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--lumina-text-muted)',
                      flexShrink: 0,
                    }}>
                      {formatTimestamp(ev.timestamp)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Detail Panel */}
      {selectedEvidence !== null && evidenceList[selectedEvidence] && (
        <EvidenceDetailPanel
          evidence={{
            ...evidenceList[selectedEvidence],
            session_id: session.sessionId,
          }}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  );
}
