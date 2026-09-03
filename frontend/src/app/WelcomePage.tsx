import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';

export function WelcomePage() {
  const navigate = useNavigate();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 7rem)',
        textAlign: 'center',
        padding: 'var(--space-8)',
      }}
    >
      <h1
        style={{
          fontSize: 'var(--text-4xl)',
          fontWeight: 900,
          letterSpacing: 'var(--tracking-wider)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-4)',
          animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) both',
        }}
      >
        LUMINA
      </h1>

      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          fontWeight: 600,
          marginBottom: 'var(--space-2)',
        }}
      >
        Digital Forensics × Human Safety × Calm Intervention
      </p>

      <p
        style={{
          fontSize: 'var(--text-base)',
          color: 'var(--lumina-text-secondary)',
          maxWidth: '28rem',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: 'var(--space-10)',
          animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) 100ms both',
        }}
      >
        Evidence-driven protection against digital arrest scams and social engineering.
      </p>

      <Button
        variant="primary"
        size="lg"
        onClick={() => navigate('/consent')}
        style={{ animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) 200ms both' }}
      >
        Get Started
      </Button>
    </div>
  );
}
