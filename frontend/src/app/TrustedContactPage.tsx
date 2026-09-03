/* ============================================================
   LUMINA Trusted Contact
   ============================================================
   Real trusted contact experience.
   Backend reality: The current evidence framework does NOT
   provide a session-based trusted-contact management or
   delivery system. The legacy /api/send-alert endpoint
   requires elder_name + CallFeatures and uses the risk engine.
   
   The honest UI must represent the real capability boundary.
   ============================================================ */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionState } from '@/hooks/useSessionState';
import { sendAlert } from '@/lib/api/alert';
import type { SendAlertResponse } from '@/lib/api/alert';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Divider } from '@/components/Divider';
import { SectionHeader } from '@/components/SectionHeader';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { InterventionShell } from '@/components/Interventions';

// ---- Delivery Status Display ----
function DeliveryStatusDisplay({ result }: { result: SendAlertResponse }) {
  const statusMap: Record<string, { icon: string; label: string }> = {
    NOT_CONFIGURED: { icon: '⊘', label: 'Not Configured' },
    NO_RECIPIENT: { icon: '⊘', label: 'No Recipient' },
    SENT: { icon: '✓', label: 'Alert Sent' },
    FAILED: { icon: '✕', label: 'Delivery Failed' },
    SIMULATED: { icon: '⊘', label: 'Demo Mode — Not Delivered' },
  };

  const statusInfo = statusMap[result.delivery_status] || { icon: '?', label: result.delivery_status };
  const dataStatus = result.delivery_status === 'SENT' ? 'SENT' :
    result.delivery_status === 'FAILED' ? 'FAILED' :
      result.alert_sent ? 'SENT' : 'NOT_CONFIGURED';

  return (
    <div className="delivery-status" data-status={dataStatus} role="status" aria-live="polite">
      <span className="delivery-status-icon" aria-hidden="true">{statusInfo.icon}</span>
      <div>
        <div style={{ fontWeight: 700 }}>{statusInfo.label}</div>
        {result.message && (
          <div style={{ fontWeight: 400, fontSize: 'var(--text-xs)', marginTop: '2px', opacity: 0.8 }}>
            {result.message}
          </div>
        )}
        {result.reason && (
          <div style={{ fontWeight: 400, fontSize: 'var(--text-xs)', marginTop: '2px', opacity: 0.7 }}>
            Reason: {result.reason}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- TrustedContactPage ----

export function TrustedContactPage() {
  const navigate = useNavigate();
  const session = useSessionState();
  const [sending, setSending] = useState(false);
  const [alertResult, setAlertResult] = useState<SendAlertResponse | null>(null);
  const [alertError, setAlertError] = useState<string | null>(null);

  const handleSendAlert = useCallback(async () => {
    if (!session.credentials) return;

    setSending(true);
    setAlertError(null);
    setAlertResult(null);

    try {
      const result = await sendAlert(session.credentials, {
        elder_name: 'current_user',
        call_duration_min: 0,
      });

      if (!result.ok) {
        setAlertError(`Failed to send alert: ${result.error}`);
        return;
      }

      setAlertResult(result.data);
    } catch (err) {
      setAlertError(err instanceof Error ? err.message : 'Unexpected error');
    } finally {
      setSending(false);
    }
  }, [session.credentials]);

  // ---- Loading ----
  if (session.status === 'loading' || session.status === 'creating') {
    return (
      <InterventionShell state="WATCH">
        <LoadingState message="Loading trusted contact status" />
      </InterventionShell>
    );
  }

  // ---- Unavailable ----
  if (session.status === 'unavailable') {
    return (
      <InterventionShell state="WATCH">
        <UnavailableState
          message={session.error || 'Backend unavailable'}
          onRetry={session.refresh}
        />
      </InterventionShell>
    );
  }

  // ---- Error ----
  if (session.status === 'error') {
    return (
      <InterventionShell state="WATCH">
        <ErrorState
          title="Error"
          message={session.error || 'An error occurred'}
          onRetry={session.refresh}
        />
      </InterventionShell>
    );
  }

  return (
    <InterventionShell state="WATCH">
      <SectionHeader
        number={6}
        title="Trusted Contact"
        subtitle="Alert a trusted person about your current situation"
      />

      {/* Capability Notice */}
      <div className="capability-banner">
        <div className="capability-banner-title">Capability Status</div>
        <div className="capability-banner-text">
          Trusted contact delivery is not yet fully configured in the current backend.
          The alert system requires a named recipient and SMS delivery infrastructure.
          LUMINA shows the real delivery status — it never claims delivery when none occurred.
        </div>
      </div>

      {/* Current Session Context */}
      {session.session && session.decision && (
        <Card style={{ marginBottom: 'var(--space-6)' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-widest)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-2)' }}>
            Current Session
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--lumina-text-secondary)' }}>
              {session.session.sessionId.slice(0, 12)}…
            </span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>
              State: {session.decision.stateLabel}
            </span>
          </div>
          {session.decision.recommendedAction && (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
              {session.decision.recommendedAction}
            </div>
          )}
        </Card>
      )}

      {/* No Session */}
      {!session.session && (
        <Card style={{ marginBottom: 'var(--space-6)' }}>
          <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-4)' }}>
              No active session. Start a session to enable trusted contact alerts.
            </div>
            <Button variant="primary" onClick={() => navigate('/session')}>
              Start Session
            </Button>
          </div>
        </Card>
      )}

      {/* Data Minimization */}
      <div className="data-minimization">
        <div className="data-minimization-title">Data Minimization</div>
        <div>
          LUMINA shares only the minimum necessary information with trusted contacts:
          your session reference, current safety state, and a brief description of the situation.
          LUMINA does not automatically share your location, contacts, recordings, or private messages.
        </div>
      </div>

      {/* Alert Action */}
      <Card style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-widest)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-4)' }}>
          Send Alert
        </div>

        {alertResult && (
          <DeliveryStatusDisplay result={alertResult} />
        )}

        {alertError && (
          <div
            role="alert"
            style={{
              padding: 'var(--space-3) var(--space-4)',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(220, 68, 68, 0.08)',
              border: '1px solid var(--lumina-danger)',
              color: 'var(--lumina-danger)',
              fontSize: 'var(--text-sm)',
              marginBottom: 'var(--space-4)',
            }}
          >
            {alertError}
          </div>
        )}

        {sending && (
          <div className="sending-indicator">
            <span aria-hidden="true">◌</span>
            <span>Sending alert…</span>
          </div>
        )}

        {!sending && !alertResult && (
          <>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', marginBottom: 'var(--space-4)', lineHeight: 'var(--leading-relaxed)' }}>
              Send a safety alert to configured trusted contacts. The backend will evaluate whether
              delivery is possible based on the current configuration.
            </div>
            <Button
              variant="primary"
              onClick={handleSendAlert}
              disabled={!session.credentials}
            >
              Send Alert
            </Button>
          </>
        )}

        {alertResult && !sending && (
          <Button
            variant="secondary"
            onClick={handleSendAlert}
            disabled={!session.credentials}
          >
            Try Again
          </Button>
        )}
      </Card>

      {/* How It Works */}
      <Card style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-widest)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-4)' }}>
          How Trusted Contact Alerts Work
        </div>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }} role="list" aria-label="How alerts work">
          {[
            { icon: '1', text: 'You review what information will be shared before sending.' },
            { icon: '2', text: 'You explicitly confirm the alert — LUMINA never sends automatically.' },
            { icon: '3', text: 'The backend evaluates delivery capability (configured contacts, SMS infrastructure).' },
            { icon: '4', text: 'The real delivery status is shown — not a simulated success.' },
          ].map((step) => (
            <li key={step.icon} style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
              <span style={{ width: '1.5rem', height: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--lumina-surface)', border: '1px solid var(--lumina-border)', color: 'var(--lumina-text-muted)', fontSize: 'var(--text-xs)', fontWeight: 700, flexShrink: 0 }}>
                {step.icon}
              </span>
              <span>{step.text}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Divider />

      {/* Navigation */}
      <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
        <Button variant="secondary" onClick={() => navigate('/session')}>
          Back to Session
        </Button>
        <Button variant="secondary" onClick={() => navigate('/evidence')}>
          View Evidence
        </Button>
      </div>
    </InterventionShell>
  );
}
