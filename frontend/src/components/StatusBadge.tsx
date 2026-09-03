import type { SafetyState } from '@/types/safety';
import { SAFETY_STATE_LABELS, SAFETY_STATE_COLORS } from '@/types/safety';

interface StatusBadgeProps {
  state: SafetyState;
  /** Show label text */
  showLabel?: boolean;
  /** Custom label override */
  label?: string;
  /** Badge size */
  size?: 'sm' | 'md';
  style?: React.CSSProperties;
}

export function StatusBadge({
  state,
  showLabel = true,
  label,
  size = 'md',
  style,
}: StatusBadgeProps) {
  const displayLabel = label ?? SAFETY_STATE_LABELS[state];
  const color = SAFETY_STATE_COLORS[state];

  const sizeStyles = size === 'sm'
    ? { padding: '2px 8px', fontSize: 'var(--text-xs)' }
    : { padding: '4px 12px', fontSize: 'var(--text-xs)' };

  return (
    <span
      role="status"
      aria-label={`Status: ${displayLabel}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        fontWeight: 700,
        letterSpacing: 'var(--tracking-wider)',
        textTransform: 'uppercase',
        color,
        border: `1px solid ${color}`,
        borderRadius: 'var(--radius-full)',
        whiteSpace: 'nowrap',
        lineHeight: 1.4,
        ...sizeStyles,
        ...style,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
        }}
      />
      {showLabel && displayLabel}
    </span>
  );
}
