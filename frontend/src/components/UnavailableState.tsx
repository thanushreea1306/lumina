import { Button } from './Button';

interface UnavailableStateProps {
  /** What is unavailable */
  title?: string;
  /** Message */
  message?: string;
  /** Retry action */
  onRetry?: () => void;
  style?: React.CSSProperties;
}

export function UnavailableState({
  title = 'Backend Unavailable',
  message = 'Unable to connect to the LUMINA backend. Please ensure the server is running and try again.',
  onRetry,
  style,
}: UnavailableStateProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-16) var(--space-6)',
        textAlign: 'center',
        minHeight: '60vh',
        ...style,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: '4rem',
          height: '4rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 'var(--radius-xl)',
          background: 'var(--lumina-surface)',
          border: '1px solid var(--lumina-border)',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-6)',
          fontSize: '1.5rem',
        }}
      >
        ◌
      </div>
      <h2
        style={{
          fontSize: 'var(--text-2xl)',
          fontWeight: 800,
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-3)',
        }}
      >
        {title}
      </h2>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          maxWidth: '28rem',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: onRetry ? 'var(--space-6)' : 0,
        }}
      >
        {message}
      </p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Reconnect
        </Button>
      )}
    </div>
  );
}
