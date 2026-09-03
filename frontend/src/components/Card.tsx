import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  /** Elevated surface variant */
  elevated?: boolean;
  /** Add subtle glow effect */
  glow?: boolean;
  /** Custom class name */
  className?: string;
  /** Inline styles override */
  style?: React.CSSProperties;
}

export function Card({ children, elevated = false, glow = false, className, style }: CardProps) {
  return (
    <div
      role="region"
      className={className}
      style={{
        background: elevated ? 'var(--lumina-surface-elevated)' : 'var(--lumina-surface)',
        border: '1px solid var(--lumina-border)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-6)',
        boxShadow: glow
          ? 'var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.03)'
          : 'var(--shadow-sm)',
        transition: `box-shadow var(--duration-normal) var(--ease-out)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
