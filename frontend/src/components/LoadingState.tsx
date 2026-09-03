interface LoadingStateProps {
  /** Loading message for screen readers */
  message?: string;
  /** Show as full-page or inline */
  fullPage?: boolean;
  style?: React.CSSProperties;
}

export function LoadingState({ message = 'Loading…', fullPage = false, style }: LoadingStateProps) {
  const content = (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-4)',
        padding: fullPage ? 'var(--space-20) var(--space-4)' : 'var(--space-8) var(--space-4)',
        ...style,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: '2rem',
          height: '2rem',
          border: '2px solid var(--lumina-border-strong)',
          borderTopColor: 'var(--lumina-danger)',
          borderRadius: '50%',
          animation: 'luminaSpin 0.8s linear infinite',
        }}
      />
      <p
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          fontWeight: 600,
        }}
      >
        <span className="sr-only">{message}</span>
        {message}
      </p>
    </div>
  );

  if (fullPage) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
        }}
      >
        {content}
      </div>
    );
  }

  return content;
}
