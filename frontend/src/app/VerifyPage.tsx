/* ============================================================
   LUMINA VERIFY Intervention
   ============================================================
   Help the user independently verify a claim before proceeding.
   "Something needs verification."
   NOT "This person is a scammer."
   ============================================================ */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionState } from '@/hooks/useSessionState';
import { userResponse } from '@/lib/api/sessions';
import { StatusBadge } from '@/components/StatusBadge';
import { CaseID } from '@/components/CaseID';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Divider } from '@/components/Divider';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import {
  InterventionShell,
  InterventionHeader,
  ReasonList,
  SafetyGuidance,
  HighRiskActionList,
  ResponseOptions,
  MissingInfoList,
} from '@/components/Interventions';

// ---- VERIFY-specific guidance ----
function getVerifyGuidance(reasonCodes: string[]) {
  const items: Array<{ text: string; type: 'safe' | 'warn' }> = [];

  items.push({ text: 'Verify the caller\'s identity independently using an official contact method.', type: 'safe' });
  items.push({ text: 'Do not use phone numbers, links, or details provided by the caller.', type: 'warn' });
  items.push({ text: 'Contact the organisation directly using a number from their official website.', type: 'safe' });
  items.push({ text: 'Do not share OTPs, passwords, or PINs with anyone.', type: 'warn' });
  items.push({ text: 'Do not install remote-access software at anyone\'s request.', type: 'warn' });

  if (reasonCodes.some((r) => r.includes('money') || r.includes('payment') || r.includes('transfer'))) {
    items.push({ text: 'Do not send money or make payments until identity is independently confirmed.', type: 'warn' });
  }
  if (reasonCodes.some((r) => r.includes('OTP') || r.includes('code') || r.includes('password'))) {
    items.push({ text: 'Never share one-time passwords or verification codes.', type: 'warn' });
  }

  return items;
}

// ---- VERIFY Response Options ----
const VERIFY_RESPONSES = [
  {
    action: 'verification_completed',
    response: 'verified_safe',
    label: 'I verified independently — it\'s legitimate',
    description: 'You confirmed the contact through an official, independent channel.',
    icon: '✓',
    variant: 'safe' as const,
  },
  {
    action: 'verification_completed',
    response: 'verified_suspicious',
    label: 'I verified independently — it\'s suspicious',
    description: 'The independent check revealed inconsistencies or impossibilities.',
    icon: '⚠',
    variant: 'danger' as const,
  },
  {
    action: 'verification_declined',
    response: 'will_not_verify',
    label: 'I cannot verify right now',
    description: 'Pause the interaction until you can verify independently.',
    icon: '⏸',
    variant: 'primary' as const,
  },
];

// ---- VerifyPage ----

export function VerifyPage() {
  const navigate = useNavigate();
  const session = useSessionState();
  const [submitting, setSubmitting] = useState(false);
  const [submittedResponse, setSubmittedResponse] = useState<string | null>(null);
  const [responseError, setResponseError] = useState<string | null>(null);

  const handleResponse = useCallback(async (action: string, response: string) => {
    const sessionId = session.session?.sessionId;
    if (!sessionId || !session.credentials) return;

    setSubmitting(true);
    setResponseError(null);

    try {
      const result = await userResponse(session.credentials, sessionId, {
        action,
        response,
      });

      if (!result.ok) {
        setResponseError(`Failed to submit response: ${result.error}`);
        setSubmitting(false);
        return;
      }

      setSubmittedResponse(response);
      await session.refresh();
    } catch (err) {
      setResponseError(err instanceof Error ? err.message : 'Unexpected error');
    } finally {
      setSubmitting(false);
    }
  }, [session]);

  // ---- Loading ----
  if (session.status === 'loading' || session.status === 'creating') {
    return (
      <InterventionShell state="VERIFY">
        <LoadingState message="Loading verification status" />
      </InterventionShell>
    );
  }

  // ---- Unavailable ----
  if (session.status === 'unavailable') {
    return (
      <InterventionShell state="VERIFY">
        <UnavailableState message={session.error || 'Backend unavailable'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- Error ----
  if (session.status === 'error') {
    return (
      <InterventionShell state="VERIFY">
        <ErrorState title="Error" message={session.error || 'An error occurred'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- No active session ----
  if (session.status === 'idle' || !session.session || !session.decision) {
    return (
      <InterventionShell state="VERIFY">
        <div className="no-session-banner">
          <div className="intervention-icon" data-state="VERIFY" aria-hidden="true" style={{ margin: '0 auto var(--space-4)' }}>🔍</div>
          <h2>No Active Safety Session</h2>
          <p>Start a session from the Session page to access the Verify intervention.</p>
          <Button variant="primary" onClick={() => navigate('/session')}>
            Go to Session
          </Button>
        </div>
      </InterventionShell>
    );
  }

  // ---- Decision unavailable ----
  if (!session.decision) {
    return (
      <InterventionShell state="VERIFY">
        <div className="decision-unavailable">
          <h2>Safety Decision Unavailable</h2>
          <p>The safety decision could not be retrieved. This may indicate a backend issue.</p>
          <Button variant="primary" onClick={session.refresh}>
            Retry
          </Button>
        </div>
      </InterventionShell>
    );
  }

  const { decision } = session;
  const guidance = getVerifyGuidance(decision.reasonCodes);

  return (
    <InterventionShell state="VERIFY">
      <InterventionHeader
        state="VERIFY"
        icon="🔍"
        title="Verify"
        subtitle="Verify the caller's identity independently before proceeding. Do not rely on information they provide."
      />

      {/* Case Status Bar */}
      <div className="session-status-bar" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ color: 'var(--lumina-text-muted)' }}>CASE</span>
          <CaseID sessionId={session.session.sessionId} />
        </div>
        <span aria-hidden="true" style={{ color: 'var(--lumina-border-strong)' }}>|</span>
        <StatusBadge state={decision.state} label={decision.stateLabel} />
      </div>

      {/* Reason Codes */}
      <ReasonList reasons={decision.reasonCodes} state="VERIFY" />

      {/* Recommended Action */}
      {decision.recommendedAction && (
        <Card style={{ marginBottom: 'var(--space-4)', borderLeftColor: 'var(--lumina-warning)', borderLeftWidth: '3px' }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-widest)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-2)' }}>
            Recommended Action
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
            {decision.recommendedAction}
          </div>
        </Card>
      )}

      {/* High Risk Actions */}
      <HighRiskActionList actions={decision.highRiskActions} />

      {/* Missing Information */}
      <MissingInfoList items={decision.missingInformation} />

      {/* Safety Guidance */}
      <SafetyGuidance title="What You Should Do" items={guidance} />

      <Divider />

      {/* Response Section */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-widest)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-4)' }}>
          Your Response
        </div>

        {submittedResponse ? (
          <div className="response-submitted" role="status" aria-live="polite">
            <span className="response-submitted-icon" aria-hidden="true">✓</span>
            <span>
              Response recorded: {submittedResponse === 'verified_safe' ? 'Verified Safe' :
                submittedResponse === 'verified_suspicious' ? 'Verified Suspicious' :
                  'Will Not Verify'}
            </span>
          </div>
        ) : (
          <>
            {responseError && (
              <div role="alert" style={{ padding: 'var(--space-3) var(--space-4)', borderRadius: 'var(--radius-md)', background: 'rgba(220, 68, 68, 0.08)', border: '1px solid var(--lumina-danger)', color: 'var(--lumina-danger)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                {responseError}
              </div>
            )}
            <ResponseOptions
              options={VERIFY_RESPONSES}
              onSelect={handleResponse}
              submitting={submitting}
            />
          </>
        )}
      </div>

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
