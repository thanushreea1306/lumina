/* ============================================================
   LUMINA Incident Entry Page
   ============================================================
   The entry point for the Incident Copilot experience.
   "Something suspicious happened? LUMINA can help you understand
   what happened and what to do next."
   ============================================================ */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIncidentState } from '@/hooks/useIncidentState';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';

export function IncidentEntryPage() {
  const {
    status,
    incident,
    error,
    errorCode,
    startNewIncident,
  } = useIncidentState();
  const navigate = useNavigate();

  // Navigate to incident view when incident is loaded
  useEffect(() => {
    if (status === 'active' && incident) {
      navigate('/incident', { replace: true });
    }
  }, [status, incident, navigate]);

  if (status === 'loading' || status === 'creating') {
    return <LoadingState message={status === 'creating' ? 'Starting incident…' : 'Loading…'} />;
  }

  if (status === 'error' && error) {
    return (
      <ErrorState
        title="Could not start incident"
        message={error}
        status={errorCode ?? undefined}
        onRetry={startNewIncident}
      />
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        padding: 'var(--space-6)',
      }}
    >
      <Card
        elevated
        style={{
          maxWidth: '32rem',
          width: '100%',
          textAlign: 'center',
          padding: 'var(--space-10) var(--space-6)',
        }}
      >
        {/* Icon */}
        <div
          aria-hidden="true"
          style={{
            width: '3.5rem',
            height: '3.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 'var(--radius-lg)',
            background: 'var(--lumina-investigation-soft)',
            border: '1px solid rgba(155, 123, 219, 0.3)',
            color: 'var(--lumina-investigation)',
            margin: '0 auto var(--space-6)',
            fontSize: 'var(--text-2xl)',
          }}
        >
          ◆
        </div>

        <h1
          style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-4)',
          }}
        >
          Incident Copilot
        </h1>

        <p
          style={{
            fontSize: 'var(--text-base)',
            color: 'var(--lumina-text-secondary)',
            lineHeight: 'var(--leading-relaxed)',
            marginBottom: 'var(--space-2)',
            maxWidth: '28rem',
            margin: '0 auto var(--space-2)',
          }}
        >
          Something suspicious happened?
        </p>
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            lineHeight: 'var(--leading-relaxed)',
            marginBottom: 'var(--space-8)',
            maxWidth: '28rem',
            margin: '0 auto var(--space-8)',
          }}
        >
          LUMINA can help you understand what happened, what may be at risk,
          and what to do next.
        </p>

        <Button
          variant="primary"
          size="lg"
          onClick={startNewIncident}
          style={{ width: '100%' }}
        >
          Start Incident
        </Button>

        <div
          style={{
            marginTop: 'var(--space-6)',
            textAlign: 'left',
            background: 'rgba(0, 0, 0, 0.15)',
            border: '1px solid var(--lumina-border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-4)',
          }}
        >
          <div
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--lumina-text-muted)',
              marginBottom: 'var(--space-3)',
            }}
          >
            What you can share
          </div>
          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-2)',
            }}
          >
            <li style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
              <span aria-hidden="true" style={{ color: 'var(--lumina-system)', flexShrink: 0 }}>◉</span>
              Live recording from this device, only while you choose to record
            </li>
            <li style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
              <span aria-hidden="true" style={{ color: 'var(--lumina-system)', flexShrink: 0 }}>◉</span>
              An audio file you already have
            </li>
            <li style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
              <span aria-hidden="true" style={{ color: 'var(--lumina-system)', flexShrink: 0 }}>◉</span>
              A transcript you type or paste
            </li>
          </ul>
          <p
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--lumina-text-muted)',
              marginTop: 'var(--space-3)',
              lineHeight: 'var(--leading-relaxed)',
              marginBottom: 0,
            }}
          >
            LUMINA never records your calls without asking — you choose what to
            share, and everything stays on your device's private incident record.
          </p>
        </div>
      </Card>
    </div>
  );
}
