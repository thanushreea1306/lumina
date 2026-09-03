/* ============================================================
   LUMINA Recovery Summary
   ============================================================
   Recovery is entered after a safety session/outcome.
   Uses real session data only. Never fabricates recovery.
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { useSessionState } from '@/hooks/useSessionState';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Divider } from '@/components/Divider';
import { StatusBadge } from '@/components/StatusBadge';
import { CaseID } from '@/components/CaseID';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { InterventionShell } from '@/components/Interventions';
import type { SafetyState } from '@/types/safety';

// ---- Next-step guidance based on actual observations ----
function getNextSteps(observations: string[]): Array<{ icon: string; title: string; description: string; urgent: boolean }> {
  const steps: Array<{ icon: string; title: string; description: string; urgent: boolean }> = [];

  if (observations.some((o) => o === 'MONEY_REQUEST' || o === 'BANK_TRANSFER_REQUEST' || o === 'CRYPTO_REQUEST' || o === 'GIFT_CARD_REQUEST')) {
    steps.push({
      icon: '🏦',
      title: 'Contact your bank',
      description: 'If you sent money or shared financial details, contact your bank or financial institution through an independently verified channel (use a number from their official website, not one provided by the caller).',
      urgent: true,
    });
  }

  if (observations.some((o) => o === 'OTP_REQUEST' || o === 'PASSWORD_REQUEST')) {
    steps.push({
      icon: '🔐',
      title: 'Change your credentials',
      description: 'If you shared a one-time password, PIN, or login credentials, change them immediately through the official service. Contact the service provider if you suspect unauthorized access.',
      urgent: true,
    });
  }

  if (observations.some((o) => o === 'REMOTE_ACCESS_REQUEST' || o === 'APP_INSTALL_REQUEST')) {
    steps.push({
      icon: '📱',
      title: 'Remove remote access software',
      description: 'If you installed remote-access software or granted screen-sharing access, disconnect from the internet, uninstall the software, and consider having your device checked by a trusted technical advisor.',
      urgent: true,
    });
  }

  if (observations.some((o) => o === 'IDENTITY_DOCUMENT_REQUEST')) {
    steps.push({
      icon: '🪪',
      title: 'Review identity documents',
      description: 'If you shared identity documents, monitor for unauthorized use. Consider reporting to relevant authorities if you believe your documents may be misused.',
      urgent: false,
    });
  }

  // Always provide general guidance
  steps.push({
    icon: '📋',
    title: 'Document what happened',
    description: 'Write down what you remember: phone numbers, names used, what was requested, and any actions you took. This may be useful if you need to report the incident.',
    urgent: false,
  });

  steps.push({
    icon: '📞',
    title: 'Report if appropriate',
    description: 'If you believe you were targeted by fraud, consider reporting to your local authorities or consumer protection agency through an official channel.',
    urgent: false,
  });

  return steps;
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function RecoveryPage() {
  const navigate = useNavigate();
  const session = useSessionState();

  // ---- Loading ----
  if (session.status === 'loading' || session.status === 'creating') {
    return (
      <InterventionShell state="RECOVERY">
        <LoadingState message="Loading recovery information" />
      </InterventionShell>
    );
  }

  // ---- Unavailable ----
  if (session.status === 'unavailable') {
    return (
      <InterventionShell state="RECOVERY">
        <UnavailableState message={session.error || 'Backend unavailable'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- Error ----
  if (session.status === 'error') {
    return (
      <InterventionShell state="RECOVERY">
        <ErrorState title="Error" message={session.error || 'An error occurred'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- No session ----
  if (!session.session || !session.decision) {
    return (
      <InterventionShell state="RECOVERY">
        <div className="animate-fade-in">
          <EmptyState
            title="No Active Session"
            description="Complete a safety session to view recovery guidance. Recovery information is based on what was actually observed during your session."
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            }
            action={
              <Button variant="primary" onClick={() => navigate('/session')}>
                Start Session
              </Button>
            }
          />
        </div>
      </InterventionShell>
    );
  }

  const decision = session.decision;
  const observations = decision.observations || [];
  const nextSteps = getNextSteps(observations);

  return (
    <InterventionShell state="RECOVERY">
      <div className="animate-fade-in">
        {/* Section header */}
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
            07
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{
              fontSize: 'var(--text-xl)',
              fontWeight: 800,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text)',
            }}>
              Session Review
            </h1>
            <p style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-muted)',
              marginTop: 'var(--space-1)',
            }}>
              Review what happened and decide what to do next
            </p>
          </div>
          <StatusBadge state={decision.state as SafetyState} />
        </div>

        {/* Session Summary */}
        <Card style={{ marginBottom: 'var(--space-4)' }}>
          <div style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-3)',
          }}>
            Session Summary
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span style={{ color: 'var(--lumina-text-muted)', fontSize: 'var(--text-xs)' }}>CASE</span>
              <CaseID sessionId={session.session.sessionId} />
            </div>
            {session.session.startedAt && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ color: 'var(--lumina-text-muted)', fontSize: 'var(--text-xs)' }}>STARTED</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--lumina-text-secondary)' }}>
                  {formatTimestamp(session.session.startedAt)}
                </span>
              </div>
            )}
          </div>
          {decision.recommendedAction && (
            <div style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
              padding: 'var(--space-3)',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: 'var(--radius-md)',
            }}>
              {decision.recommendedAction}
            </div>
          )}
        </Card>

        {/* What Was Observed */}
        {observations.length > 0 && (
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-3)',
            }}>
              What Was Observed
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
              {observations.map((obs: string) => (
                <span
                  key={obs}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-full)',
                    background: 'var(--lumina-warning-soft)',
                    border: '1px solid rgba(217, 164, 65, 0.2)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    color: 'var(--lumina-warning)',
                    letterSpacing: 'var(--tracking-wide)',
                  }}
                >
                  {obs.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c: string) => c.toUpperCase())}
                </span>
              ))}
            </div>
          </Card>
        )}

        {/* Reason Codes */}
        {decision.reasonCodes.length > 0 && (
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-3)',
            }}>
              Why This State Was Reached
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }} role="list" aria-label="Reasons for safety state">
              {decision.reasonCodes.map((reason: string, i: number) => (
                <li key={i} style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-2) 0',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--lumina-text-secondary)',
                  lineHeight: 'var(--leading-relaxed)',
                }}>
                  <span aria-hidden="true" style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'var(--lumina-system)',
                    flexShrink: 0,
                    marginTop: '0.4em',
                  }} />
                  {reason}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Next Steps */}
        <Card style={{ marginBottom: 'var(--space-4)' }}>
          <div style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-4)',
          }}>
            Recommended Next Steps
          </div>
          <div role="list" aria-label="Recommended next steps">
            {nextSteps.map((step, i) => (
              <div
                key={i}
                role="listitem"
                style={{
                  display: 'flex',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-3) 0',
                  borderBottom: i < nextSteps.length - 1 ? '1px solid var(--lumina-border-subtle)' : 'none',
                }}
              >
                <span aria-hidden="true" style={{
                  fontSize: '1.2rem',
                  flexShrink: 0,
                  width: '2rem',
                  height: '2rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 'var(--radius-md)',
                  background: step.urgent ? 'rgba(220, 68, 68, 0.08)' : 'var(--lumina-surface)',
                  border: `1px solid ${step.urgent ? 'rgba(220, 68, 68, 0.2)' : 'var(--lumina-border-subtle)'}`,
                }}>
                  {step.icon}
                </span>
                <div>
                  <div style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: step.urgent ? 'var(--lumina-danger)' : 'var(--lumina-text)',
                    marginBottom: '2px',
                  }}>
                    {step.title}
                  </div>
                  <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--lumina-text-muted)',
                    lineHeight: 'var(--leading-relaxed)',
                  }}>
                    {step.description}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Evidence Summary */}
        {decision.evidenceCount > 0 && (
          <Card style={{ marginBottom: 'var(--space-4)' }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-3)',
            }}>
              Evidence Collected
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--lumina-system)' }}>
                  {decision.evidenceCount}
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>Pieces</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--lumina-investigation)' }}>
                  {observations.length}
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>Observations</div>
              </div>
              {decision.highRiskActions.length > 0 && (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: 'var(--lumina-danger)' }}>
                    {decision.highRiskActions.length}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>High-Risk Actions</div>
                </div>
              )}
            </div>
          </Card>
        )}

        <Divider />

        {/* Navigation */}
        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', marginTop: 'var(--space-4)' }}>
          <Button variant="primary" onClick={() => navigate('/evidence')}>
            View Evidence
          </Button>
          <Button variant="secondary" onClick={() => navigate('/home')}>
            Return Home
          </Button>
          <Button variant="secondary" onClick={() => navigate('/session')}>
            New Session
          </Button>
        </div>
      </div>
    </InterventionShell>
  );
}
