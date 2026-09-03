import { Button } from './Button';

interface ErrorStateProps {
  /** Error title */
  title: string;
  /** Error detail / message */
  message: string;
  /** Retry action */
  onRetry?: () => void;
  /** HTTP status code */
  status?: number;
  style?: React.CSSProperties;
}

export function ErrorState({ title, message, onRetry, status, style }: ErrorStateProps) {
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-12) var(--space-6)',
        textAlign: 'center',
        ...style,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: '3rem',
          height: '3rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 'var(--radius-lg)',
          background: 'var(--lumina-danger-soft)',
          border: '1px solid rgba(224, 28, 43, 0.3)',
          color: 'var(--lumina-danger)',
          marginBottom: 'var(--space-4)',
          fontSize: 'var(--text-xl)',
          fontWeight: 800,
        }}
      >
        {status ? `HTTP ${status}` : '⚠'}
      </div>
      <h3
        style={{
          fontSize: 'var(--text-lg)',
          fontWeight: 700,
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-2)',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          maxWidth: '24rem',
          lineHeight: 'var(--leading-relaxed)',
          marginBottom: onRetry ? 'var(--space-6)' : 0,
        }}
      >
        {message}
      </p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
