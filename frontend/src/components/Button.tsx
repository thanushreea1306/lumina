import { type ButtonHTMLAttributes, forwardRef } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_STYLES: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: 'var(--lumina-danger)',
    color: '#fff',
    border: '1px solid var(--lumina-danger)',
  },
  secondary: {
    background: 'var(--lumina-surface-elevated)',
    color: 'var(--lumina-text)',
    border: '1px solid var(--lumina-border-strong)',
  },
  danger: {
    background: 'transparent',
    color: 'var(--lumina-danger)',
    border: '1px solid var(--lumina-danger)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--lumina-text-secondary)',
    border: '1px solid transparent',
  },
};

const SIZE_STYLES: Record<ButtonSize, React.CSSProperties> = {
  sm: {
    padding: '0.375rem 0.75rem',
    fontSize: 'var(--text-xs)',
  },
  md: {
    padding: '0.5rem 1rem',
    fontSize: 'var(--text-sm)',
  },
  lg: {
    padding: '0.75rem 1.5rem',
    fontSize: 'var(--text-base)',
  },
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', style, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        aria-disabled={disabled || undefined}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.5rem',
          fontFamily: 'var(--font-sans)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-wide)',
          borderRadius: 'var(--radius-md)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: 'all var(--duration-normal) var(--ease-out)',
          lineHeight: 1.4,
          whiteSpace: 'nowrap',
          userSelect: 'none',
          ...VARIANT_STYLES[variant],
          ...SIZE_STYLES[size],
          ...style,
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
            (e.currentTarget as HTMLElement).style.opacity = '0.9';
            (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
          }
          props.onMouseEnter?.(e);
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.opacity = disabled ? '0.5' : '1';
          (e.currentTarget as HTMLElement).style.transform = 'none';
          props.onMouseLeave?.(e);
        }}
        {...props}
      >
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';
