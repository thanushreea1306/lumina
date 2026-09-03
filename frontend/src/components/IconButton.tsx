import { type ButtonHTMLAttributes, forwardRef } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible label for screen readers */
  'aria-label': string;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ style, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        aria-disabled={disabled || undefined}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '2.5rem',
          height: '2.5rem',
          padding: 0,
          background: 'transparent',
          color: 'var(--lumina-text-secondary)',
          border: '1px solid transparent',
          borderRadius: 'var(--radius-md)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: `all var(--duration-normal) var(--ease-out)`,
          ...style,
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
            (e.currentTarget as HTMLElement).style.background = 'var(--lumina-surface-hover)';
            (e.currentTarget as HTMLElement).style.color = 'var(--lumina-text)';
            (e.currentTarget as HTMLElement).style.borderColor = 'var(--lumina-border)';
          }
          props.onMouseEnter?.(e);
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.background = 'transparent';
          (e.currentTarget as HTMLElement).style.color = 'var(--lumina-text-secondary)';
          (e.currentTarget as HTMLElement).style.borderColor = 'transparent';
          props.onMouseLeave?.(e);
        }}
        {...props}
      >
        {children}
      </button>
    );
  },
);

IconButton.displayName = 'IconButton';
