import type { ReactNode } from 'react';

interface EmptyStateProps {
  /** Short heading */
  title: string;
  /** Description of the empty state */
  description: string;
  /** Optional action */
  action?: ReactNode;
  /** Optional icon element */
  icon?: ReactNode;
  style?: React.CSSProperties;
}

export function EmptyState({ title, description, action, icon, style }: EmptyStateProps) {
  return (
    <div
      role="status"
      aria-label={title}
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
      {icon && (
        <div
          style={{
            width: '3rem',
            height: '3rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 'var(--radius-lg)',
            background: 'var(--lumina-surface)',
            border: '1px solid var(--lumina-border)',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-4)',
          }}
        >
          {icon}
        </div>
      )}
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
          marginBottom: action ? 'var(--space-6)' : 0,
        }}
      >
        {description}
      </p>
      {action}
    </div>
  );
}
