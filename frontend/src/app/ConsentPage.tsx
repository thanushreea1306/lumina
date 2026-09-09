import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';

export function ConsentPage() {
  const navigate = useNavigate();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 7rem)',
        padding: 'var(--space-8)',
        animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) both',
      }}
    >
      <Card elevated style={{ maxWidth: '32rem', width: '100%' }}>
        <h2
          style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text)',
            marginBottom: 'var(--space-4)',
          }}
        >
          Data & Privacy
        </h2>

        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-secondary)',
            lineHeight: 'var(--leading-relaxed)',
            marginBottom: 'var(--space-6)',
          }}
        >
          LUMINA stores only the evidence you explicitly provide during safety
          sessions. No conversations are recorded. No personal data is sold.
          Your device is identified by a secure authenticated credential, and data is
          scoped to that device.
        </p>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
            marginBottom: 'var(--space-6)',
          }}
        >
          {[
            'Evidence you submit is device-bound and stored on the LUMINA backend',
            'Sessions are device-bound and protected by authenticated device credentials',
            'No background monitoring or tracking',
            'Account data can be deleted via the account deletion flow',
          ].map((item) => (
            <div
              key={item}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: 'var(--lumina-recovery)',
                  flexShrink: 0,
                }}
              />
              {item}
            </div>
          ))}
        </div>

        <Button
          variant="primary"
          onClick={() => navigate('/home')}
          style={{ width: '100%' }}
        >
          I Understand — Continue
        </Button>
      </Card>
    </div>
  );
}
