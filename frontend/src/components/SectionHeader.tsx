import type { ReactNode } from 'react';

interface SectionHeaderProps {
  /** Section number for forensic-style numbering */
  number?: number;
  /** Main heading text */
  title: string;
  /** Optional subtitle / description */
  subtitle?: string;
  /** Right-side content */
  actions?: ReactNode;
  style?: React.CSSProperties;
}

export function SectionHeader({ number, title, subtitle, actions, style }: SectionHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-5)',
        paddingBottom: 'var(--space-4)',
        borderBottom: '1px solid var(--lumina-border-subtle)',
        position: 'relative',
        animation: 'luminaFadeIn var(--duration-slow) var(--ease-out) both',
        ...style,
      }}
    >
      {number !== undefined && (
        <span
          aria-hidden="true"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-sm)',
            fontWeight: 800,
            color: 'var(--lumina-danger)',
            background: 'var(--lumina-danger-soft)',
            border: '1px solid rgba(224, 28, 43, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '4px 10px',
            flexShrink: 0,
          }}
        >
          {String(number).padStart(2, '0')}
        </span>
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <h2
          style={{
            fontSize: 'var(--text-xl)',
            fontWeight: 800,
            letterSpacing: 'var(--tracking-wide)',
            textTransform: 'uppercase',
            lineHeight: 'var(--leading-tight)',
            color: 'var(--lumina-text)',
          }}
        >
          {title}
        </h2>
        {subtitle && (
          <p
            style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-muted)',
              marginTop: 'var(--space-1)',
              lineHeight: 'var(--leading-relaxed)',
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      {actions && (
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexShrink: 0 }}>
          {actions}
        </div>
      )}
    </div>
  );
}
