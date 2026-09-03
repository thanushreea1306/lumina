/* ============================================================
   LUMINA PROTECT Intervention
   ============================================================
   Highest urgency state. Prioritizes immediate protective action.
   "Do not proceed until you have independently verified this."
   NOT "100% scam" or "confirmed criminal."
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

// ---- PROTECT-specific guidance ----
function getProtectGuidance(reasonCodes: string[]) {
  const items: Array<{ text: string; type: 'safe' | 'warn' }> = [];

  items.push({ text: 'Stop the interaction immediately.', type: 'warn' });
  items.push({ text: 'Do not share any codes, passwords, PINs, or financial information.', type: 'warn' });
  items.push({ text: 'Do not send money or make any payments.', type: 'warn' });
  items.push({ text: 'Do not install any software or grant remote access.', type: 'warn' });
  items.push({ text: 'Do not share identity documents or personal details.', type: 'warn' });
  items.push({ text: 'You have the right to end this interaction at any time.', type: 'safe' });

  if (reasonCodes.some((r) => r.includes('OTP') || r.includes('code') || r.includes('password'))) {
    items.push({ text: 'If you already shared a code or password, change it immediately.', type: 'safe' });
  }
  if (reasonCodes.some((r) => r.includes('money') || r.includes('payment') || r.includes('transfer'))) {
    items.push({ text: 'If you already sent money, contact your bank immediately.', type: 'safe' });
  }
  if (reasonCodes.some((r) => r.includes('remote') || r.includes('install') || r.includes('access'))) {
    items.push({ text: 'If you installed software, disconnect from the internet and seek technical help.', type: 'safe' });
  }

  return items;
}

// ---- PROTECT Response Options ----
const PROTECT_RESPONSES = [
  {
    action: 'protect_action',
    response: 'stopped_and_secured',
    label: 'I stopped and secured my accounts',
    description: 'You ended the interaction and took protective measures.',
    icon: '🛡',
    variant: 'safe' as const,
  },
  {
    action: 'protect_action',
    response: 'need_help',
    label: 'I need help securing my information',
    description: 'Guidance will be provided to help you take protective steps.',
    icon: '⚠',
    variant: 'primary' as const,
  },
  {
    action: 'protect_action',
    response: 'will_proceed_despite_warning',
    label: 'I understand the risk but will proceed',
    description: 'LUMINA cannot block this action automatically. This is a strong warning to stop.',
    icon: '→',
    variant: 'danger' as const,
  },
];

// ---- ProtectPage ----

export function ProtectPage() {
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
      <InterventionShell state="PROTECT">
        <LoadingState message="Loading protection status" />
      </InterventionShell>
    );
  }

  // ---- Unavailable ----
  if (session.status === 'unavailable') {
    return (
      <InterventionShell state="PROTECT">
        <UnavailableState message={session.error || 'Backend unavailable'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- Error ----
  if (session.status === 'error') {
    return (
      <InterventionShell state="PROTECT">
        <ErrorState title="Error" message={session.error || 'An error occurred'} onRetry={session.refresh} />
      </InterventionShell>
    );
  }

  // ---- No active session ----
  if (session.status === 'idle' || !session.session || !session.decision) {
    return (
      <InterventionShell state="PROTECT">
        <div className="no-session-banner">
          <div className="intervention-icon" data-state="PROTECT" aria-hidden="true" style={{ margin: '0 auto var(--space-4)' }}>🛡</div>
          <h2>No Active Safety Session</h2>
          <p>Start a session from the Session page to access the Protect intervention.</p>
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
      <InterventionShell state="PROTECT">
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
  const guidance = getProtectGuidance(decision.reasonCodes);

  return (
    <InterventionShell state="PROTECT">
      <InterventionHeader
        state="PROTECT"
        icon="🛡"
        title="Protect"
        subtitle="High-risk indicators are present. Do not proceed until you have independently verified this interaction."
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

      {/* Warning Banner */}
      <div role="alert" style={{
        padding: 'var(--space-4) var(--space-5)',
        borderRadius: 'var(--radius-lg)',
        background: 'rgba(220, 68, 68, 0.08)',
        border: '1px solid var(--lumina-danger)',
        marginBottom: 'var(--space-4)',
        fontSize: 'var(--text-sm)',
        fontWeight: 600,
        color: 'var(--lumina-danger)',
        lineHeight: 'var(--leading-relaxed)',
      }}>
        Do not share codes, passwords, money, or personal information. 
        Stop the interaction and verify independently.
      </div>

      {/* Reason Codes */}
      <ReasonList reasons={decision.reasonCodes} state="PROTECT" />

      {/* Recommended Action */}
      {decision.recommendedAction && (
        <Card style={{ marginBottom: 'var(--space-4)', borderLeftColor: 'var(--lumina-danger)', borderLeftWidth: '3px' }}>
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
      <SafetyGuidance title="Immediate Protective Steps" items={guidance} />

      {/* Capability Note */}
      <div className="capability-note" style={{ marginBottom: 'var(--space-4)' }}>
        LUMINA cannot block calls, messages, or transactions automatically. 
        This is evidence-based guidance to help you protect yourself. If you are in immediate danger, 
        contact local emergency services.
      </div>

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
              Response recorded: {submittedResponse === 'stopped_and_secured' ? 'Interaction Stopped & Secured' :
                submittedResponse === 'need_help' ? 'Help Requested' :
                  'Will Proceed Despite Warning'}
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
              options={PROTECT_RESPONSES}
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
