import { SectionHeader } from '@/components/SectionHeader';
import { Card } from '@/components/Card';

export function SettingsPage() {
  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={6}
        title="Settings"
        subtitle="Configure your LUMINA experience"
      />

      <Card elevated>
        <h3
          style={{
            fontSize: 'var(--text-sm)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-wider)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-4)',
          }}
        >
          Device
        </h3>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: 'var(--space-3) 0',
          }}
        >
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
            Device Status
          </span>
          <span
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              color: 'var(--lumina-recovery)',
            }}
          >
            Registered
          </span>
        </div>
      </Card>

      <Card elevated style={{ marginTop: 'var(--space-4)' }}>
        <h3
          style={{
            fontSize: 'var(--text-sm)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-wider)',
            textTransform: 'uppercase',
            color: 'var(--lumina-text-muted)',
            marginBottom: 'var(--space-4)',
          }}
        >
          About
        </h3>
        <div
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-secondary)',
            lineHeight: 'var(--leading-relaxed)',
          }}
        >
          <p>
            LUMINA — Illuminating the Digital Arrest Trap
          </p>
          <p style={{ marginTop: 'var(--space-2)', color: 'var(--lumina-text-muted)' }}>
            Version 0.1.0
          </p>
        </div>
      </Card>
    </div>
  );
}
