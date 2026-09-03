interface DividerProps {
  style?: React.CSSProperties;
}

export function Divider({ style }: DividerProps) {
  return (
    <hr
      aria-hidden="true"
      style={{
        border: 'none',
        borderTop: '1px solid var(--lumina-border-subtle)',
        margin: 'var(--space-6) 0',
        ...style,
      }}
    />
  );
}
