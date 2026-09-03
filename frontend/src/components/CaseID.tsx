interface CaseIDProps {
  /** The session ID to display */
  sessionId: string;
  /** Whether to copy to clipboard on click */
  copyable?: boolean;
  style?: React.CSSProperties;
}

export function CaseID({ sessionId, copyable = true, style }: CaseIDProps) {
  const handleCopy = async () => {
    if (!copyable) return;
    try {
      await navigator.clipboard.writeText(sessionId);
    } catch {
      // Clipboard API may fail in some environments
    }
  };

  // Show a truncated version for display
  const truncated = sessionId.length > 12
    ? `${sessionId.slice(0, 8)}…${sessionId.slice(-4)}`
    : sessionId;

  return (
    <span
      role="text"
      aria-label={`Session ${sessionId}`}
      onClick={handleCopy}
      title={copyable ? 'Click to copy full ID' : sessionId}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--text-xs)',
        fontWeight: 600,
        letterSpacing: 'var(--tracking-wide)',
        color: 'var(--lumina-text-secondary)',
        textTransform: 'uppercase',
        cursor: copyable ? 'pointer' : 'default',
        padding: '2px 6px',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--lumina-surface)',
        border: '1px solid var(--lumina-border-subtle)',
        transition: `all var(--duration-fast) var(--ease-out)`,
        ...style,
      }}
      onMouseEnter={(e) => {
        if (copyable) {
          (e.currentTarget as HTMLElement).style.borderColor = 'var(--lumina-border-strong)';
          (e.currentTarget as HTMLElement).style.color = 'var(--lumina-text)';
        }
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--lumina-border-subtle)';
        (e.currentTarget as HTMLElement).style.color = 'var(--lumina-text-secondary)';
      }}
    >
      {truncated}
    </span>
  );
}
