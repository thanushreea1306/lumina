/* ============================================================
   LUMINA Security Settings
   ============================================================
   Reflects the actual security architecture:
   - Device registration
   - HMAC authentication
   - Protected endpoints
   Does NOT expose secrets, device IDs, or any credential material.
   ============================================================ */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';
import { hasStoredCredentials, clearStoredCredentials } from '@/lib/api/device';

export function SecurityPage() {
  const navigate = useNavigate();
  const [hasCredentials, setHasCredentials] = useState(hasStoredCredentials());
  const [showCleared, setShowCleared] = useState(false);

  const handleClearCredentials = useCallback(() => {
    clearStoredCredentials();
    setHasCredentials(false);
    setShowCleared(true);
  }, []);

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={10}
        title="Security"
        subtitle="Device identity and authentication"
      />

      {/* Device Registration */}
      <Card elevated style={{ marginBottom: 'var(--space-4)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-4)',
        }}>
          Device Registration
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--lumina-border-subtle)',
          }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
              Device Status
            </span>
            <span style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              color: hasCredentials ? 'var(--lumina-recovery)' : 'var(--lumina-text-muted)',
            }}>
              {hasCredentials ? 'Registered' : 'Not Registered'}
            </span>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: 'var(--space-3) 0',
            borderBottom: '1px solid var(--lumina-border-subtle)',
          }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
              Device Credential
            </span>
            <span style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              color: hasCredentials ? 'var(--lumina-recovery)' : 'var(--lumina-text-muted)',
            }}>
              {hasCredentials ? 'Stored Securely' : 'Not Available'}
            </span>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: 'var(--space-3) 0',
          }}>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
              API Authentication
            </span>
            <span style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              color: 'var(--lumina-recovery)',
            }}>
              HMAC-SHA256
            </span>
          </div>
        </div>
      </Card>

      {/* Security Features */}
      <Card style={{ marginBottom: 'var(--space-4)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-3)',
        }}>
          Security Features
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {[
            { label: 'Device-bound authentication', status: 'ACTIVE' },
            { label: 'HMAC request signing', status: 'ACTIVE' },
            { label: 'Per-request nonce (replay protection)', status: 'ACTIVE' },
            { label: 'Registration rate limiting', status: 'ACTIVE' },
            { label: 'HTTPS transport', status: 'REQUIRED' },
            { label: 'Credential rotation', status: 'NOT IMPLEMENTED' },
            { label: 'Device deregistration', status: 'NOT IMPLEMENTED' },
          ].map((feature) => (
            <div key={feature.label} style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: 'var(--space-2) 0',
              fontSize: 'var(--text-xs)',
            }}>
              <span style={{ color: 'var(--lumina-text-secondary)' }}>{feature.label}</span>
              <span style={{
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: feature.status === 'ACTIVE' ? 'var(--lumina-recovery)' :
                  feature.status === 'REQUIRED' ? 'var(--lumina-system)' : 'var(--lumina-text-muted)',
              }}>
                {feature.status}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Danger Zone */}
      <Card style={{ marginBottom: 'var(--space-4)', borderLeft: '3px solid var(--lumina-danger)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-danger)',
          marginBottom: 'var(--space-3)',
        }}>
          Device Identity
        </div>
        {showCleared ? (
          <div style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-recovery)',
            marginBottom: 'var(--space-4)',
          }}>
            Device credentials cleared. A new device identity will be created on next session start.
          </div>
        ) : (
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text-muted)',
            lineHeight: 'var(--leading-relaxed)',
            marginBottom: 'var(--space-4)',
          }}>
            Clearing device credentials will remove your current device identity.
            A new identity will be created when you start your next session.
            This does not affect existing session data on the server.
          </p>
        )}
        <Button
          variant="secondary"
          onClick={handleClearCredentials}
          disabled={!hasCredentials || showCleared}
        >
          {showCleared ? 'Credentials Cleared' : 'Clear Device Credentials'}
        </Button>
      </Card>

      {/* Security Notes */}
      <Card style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-3)',
        }}>
          Security Notes
        </div>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }} role="list" aria-label="Security notes">
          {[
            'Device secrets are stored locally and never transmitted to the server.',
            'Every API request is signed with HMAC-SHA256 using your device secret.',
            'A unique nonce prevents replay attacks on each request.',
            'The backend enforces registration rate limits to prevent abuse.',
            'No sensitive authentication material is displayed in the UI.',
          ].map((note, i) => (
            <li key={i} style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 'var(--space-2)',
              padding: 'var(--space-2) 0',
              fontSize: 'var(--text-xs)',
              color: 'var(--lumina-text-muted)',
              lineHeight: 'var(--leading-relaxed)',
            }}>
              <span aria-hidden="true" style={{ color: 'var(--lumina-system)', flexShrink: 0 }}>•</span>
              {note}
            </li>
          ))}
        </ul>
      </Card>

      <Button variant="secondary" onClick={() => navigate('/settings')}>
        Back to Settings
      </Button>
    </div>
  );
}
