/* ============================================================
   LUMINA Privacy Center
   ============================================================
   Clearly explains what LUMINA does and does not collect.
   Based on actual application architecture.
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';

// ---- Data categories ----
const DATA_COLLECTED = [
  {
    category: 'Session Events',
    description: 'Timestamps of session start, call events, observations, and user responses. These are stored to maintain the evidence timeline.',
    icon: '📊',
    status: 'COLLECTED' as const,
  },
  {
    category: 'User Observations',
    description: 'What you explicitly report observing (e.g., "I was asked for money"). These are user-confirmed evidence items.',
    icon: '👤',
    status: 'COLLECTED' as const,
  },
  {
    category: 'Device Identity',
    description: 'A unique device identifier used to authenticate API requests. Stored locally on your device.',
    icon: '📱',
    status: 'COLLECTED' as const,
  },
];

const DATA_NOT_COLLECTED = [
  {
    category: 'Microphone / Call Audio',
    description: 'LUMINA does not record or process audio from calls.',
    icon: '🎤',
  },
  {
    category: 'SMS / Message Content',
    description: 'LUMINA does not read, store, or analyze text messages.',
    icon: '💬',
  },
  {
    category: 'Location Data',
    description: 'LUMINA does not collect GPS coordinates or location information.',
    icon: '📍',
  },
  {
    category: 'Contact Lists',
    description: 'LUMINA does not access your address book or contact information.',
    icon: '📒',
  },
  {
    category: 'Photos / Media',
    description: 'LUMINA does not access your camera, photos, or media files.',
    icon: '📷',
  },
  {
    category: 'Browsing History',
    description: 'LUMINA does not track your web browsing activity.',
    icon: '🌐',
  },
];

export function PrivacyPage() {
  const navigate = useNavigate();

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={8}
        title="Privacy Center"
        subtitle="Understand what data LUMINA collects and how it is used"
      />

      {/* Key Principle */}
      <Card elevated style={{ marginBottom: 'var(--space-6)', borderLeft: '3px solid var(--lumina-system)' }}>
        <div style={{
          fontSize: 'var(--text-sm)',
          fontWeight: 700,
          color: 'var(--lumina-system)',
          marginBottom: 'var(--space-2)',
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
        }}>
          Privacy Principle
        </div>
        <p style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-secondary)',
          lineHeight: 'var(--leading-relaxed)',
        }}>
          LUMINA collects only the minimum data necessary to provide evidence-driven safety guidance.
          It never records audio, reads messages, or tracks your location.
          Your observations are the primary input — LUMINA analyzes patterns, not personal data.
        </p>
      </Card>

      {/* Data We Collect */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-recovery)',
          marginBottom: 'var(--space-4)',
        }}>
          Data LUMINA Collects
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {DATA_COLLECTED.map((item) => (
            <Card key={item.category}>
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <span aria-hidden="true" style={{ fontSize: '1.2rem', flexShrink: 0 }}>{item.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: 'var(--lumina-text)',
                    marginBottom: '2px',
                  }}>
                    {item.category}
                  </div>
                  <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--lumina-text-muted)',
                    lineHeight: 'var(--leading-relaxed)',
                  }}>
                    {item.description}
                  </div>
                </div>
                <span style={{
                  fontSize: 'var(--text-xs)',
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  color: 'var(--lumina-recovery)',
                  background: 'var(--lumina-recovery-soft)',
                  border: '1px solid rgba(90, 184, 122, 0.2)',
                  borderRadius: 'var(--radius-full)',
                  padding: '2px 8px',
                  flexShrink: 0,
                }}>
                  {item.status}
                </span>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Data We Do NOT Collect */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-4)',
        }}>
          Data LUMINA Does NOT Collect
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {DATA_NOT_COLLECTED.map((item) => (
            <Card key={item.category}>
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <span aria-hidden="true" style={{ fontSize: '1.2rem', flexShrink: 0 }}>{item.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 'var(--text-sm)',
                    fontWeight: 700,
                    color: 'var(--lumina-text)',
                    marginBottom: '2px',
                  }}>
                    {item.category}
                  </div>
                  <div style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--lumina-text-muted)',
                    lineHeight: 'var(--leading-relaxed)',
                  }}>
                    {item.description}
                  </div>
                </div>
                <span style={{
                  fontSize: 'var(--text-xs)',
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  color: 'var(--lumina-text-muted)',
                  background: 'var(--lumina-surface)',
                  border: '1px solid var(--lumina-border-subtle)',
                  borderRadius: 'var(--radius-full)',
                  padding: '2px 8px',
                  flexShrink: 0,
                }}>
                  NOT COLLECTED
                </span>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Data Controls */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-4)',
        }}>
          Data Controls
        </h3>
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {[
              { label: 'Export your data', status: 'NOT AVAILABLE', description: 'Data export is not available yet.' },
              { label: 'Delete your data', status: 'NOT AVAILABLE', description: 'Data deletion is not available yet.' },
              { label: 'Manage device identity', status: 'AVAILABLE', description: 'View and manage your device registration in Security settings.' },
            ].map((control) => (
              <div key={control.label} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: 'var(--space-3) 0',
                borderBottom: '1px solid var(--lumina-border-subtle)',
              }}>
                <div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
                    {control.label}
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>
                    {control.description}
                  </div>
                </div>
                <span style={{
                  fontSize: 'var(--text-xs)',
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  color: control.status === 'AVAILABLE' ? 'var(--lumina-recovery)' : 'var(--lumina-text-muted)',
                }}>
                  {control.status}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Button variant="secondary" onClick={() => navigate('/settings')}>
        Back to Settings
      </Button>
    </div>
  );
}
