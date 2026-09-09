/* ============================================================
   LUMINA Settings Hub
   ============================================================
   Organized settings: Safety, Privacy, Accessibility, Security, About
   All controls reflect real backend/frontend capability.
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { SectionHeader } from '@/components/SectionHeader';
import { hasStoredCredentials } from '@/lib/api/device';

interface SettingsLinkProps {
  label: string;
  description: string;
  path: string;
  badge?: string;
  badgeColor?: string;
}

function SettingsLink({ label, description, path, badge, badgeColor }: SettingsLinkProps) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(path)}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        width: '100%',
        padding: 'var(--space-4) 0',
        borderBottom: '1px solid var(--lumina-border-subtle)',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <div>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--lumina-text)', marginBottom: '2px' }}>
          {label}
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>
          {description}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
        {badge && (
          <span style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: 'var(--tracking-wider)',
            textTransform: 'uppercase',
            color: badgeColor || 'var(--lumina-text-muted)',
          }}>
            {badge}
          </span>
        )}
        <span style={{ color: 'var(--lumina-text-muted)', fontSize: 'var(--text-lg)' }}>›</span>
      </div>
    </button>
  );
}

export function SettingsPage() {
  const deviceRegistered = hasStoredCredentials();

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={6}
        title="Settings"
        subtitle="Configure your LUMINA experience"
      />

      {/* Account */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text)',
          marginBottom: 'var(--space-3)',
        }}>
          Account
        </h3>
        <Card>
          <SettingsLink
            label="Profile"
            description="View and edit your account information"
            path="/profile"
          />
        </Card>
      </div>

      {/* Safety */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-danger)',
          marginBottom: 'var(--space-3)',
        }}>
          Safety
        </h3>
        <Card>
          <SettingsLink
            label="Trusted Contacts"
            description="Manage alert recipients for safety situations"
            path="/onboarding"
            badge="NOT CONFIGURED"
            badgeColor="var(--lumina-warning)"
          />
          <SettingsLink
            label="Recovery"
            description="Review past sessions and next steps"
            path="/recovery"
          />
        </Card>
      </div>

      {/* Privacy */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-investigation)',
          marginBottom: 'var(--space-3)',
        }}>
          Privacy
        </h3>
        <Card>
          <SettingsLink
            label="Privacy Center"
            description="Understand what data LUMINA collects"
            path="/privacy"
          />
        </Card>
      </div>

      {/* Accessibility */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-system)',
          marginBottom: 'var(--space-3)',
        }}>
          Accessibility
        </h3>
        <Card>
          <SettingsLink
            label="Accessibility Settings"
            description="Reduce motion, larger text, high contrast"
            path="/accessibility"
          />
        </Card>
      </div>

      {/* Security */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-warning)',
          marginBottom: 'var(--space-3)',
        }}>
          Security
        </h3>
        <Card>
          <SettingsLink
            label="Security Settings"
            description="Device identity and authentication"
            path="/security"
            badge={deviceRegistered ? 'REGISTERED' : 'NOT REGISTERED'}
            badgeColor={deviceRegistered ? 'var(--lumina-recovery)' : 'var(--lumina-text-muted)'}
          />
        </Card>
      </div>

      {/* About */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-3)',
        }}>
          About
        </h3>
        <Card>
          <div style={{
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--lumina-border-subtle)',
          }}>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--lumina-text)' }}>
              LUMINA
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', marginTop: '2px' }}>
              Illuminating the Digital Arrest Trap
            </div>
          </div>
          <div style={{
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--lumina-border-subtle)',
          }}>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
              Version
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', fontFamily: 'var(--font-mono)' }}>
              0.1.0
            </div>
          </div>
          <div style={{ padding: 'var(--space-3) 0' }}>
            <div style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--lumina-text-muted)',
              lineHeight: 'var(--leading-relaxed)',
            }}>
              LUMINA is an evidence-driven personal safety system that helps users
              recognize suspicious circumstances and avoid potentially irreversible actions.
              It provides guidance based on evidence, not automated predictions.
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
