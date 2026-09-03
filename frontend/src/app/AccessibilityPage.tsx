/* ============================================================
   LUMINA Accessibility Settings
   ============================================================
   Supports preferences that actually exist in the frontend.
   Labels persistence honestly.
   ============================================================ */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';

// ---- Preference key in localStorage ----
const STORAGE_KEY = 'lumina_accessibility';

interface AccessibilityPreferences {
  reducedMotion: boolean;
  largerText: boolean;
  highContrast: boolean;
}

function loadPreferences(): AccessibilityPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...getDefaultPreferences(), ...JSON.parse(raw) };
    }
  } catch {
    // ignore
  }
  return getDefaultPreferences();
}

function getDefaultPreferences(): AccessibilityPreferences {
  return {
    reducedMotion: false,
    largerText: false,
    highContrast: false,
  };
}

function savePreferences(prefs: AccessibilityPreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // ignore
  }
}

// ---- Toggle Row Component ----
function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: 'var(--space-4) 0',
      borderBottom: '1px solid var(--lumina-border-subtle)',
    }}>
      <div style={{ flex: 1, paddingRight: 'var(--space-4)' }}>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--lumina-text)', marginBottom: '2px' }}>
          {label}
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', lineHeight: 'var(--leading-relaxed)' }}>
          {description}
        </div>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        style={{
          position: 'relative',
          width: '2.75rem',
          height: '1.5rem',
          borderRadius: 'var(--radius-full)',
          background: checked ? 'var(--lumina-recovery)' : 'var(--lumina-surface-hover)',
          border: `1px solid ${checked ? 'var(--lumina-recovery)' : 'var(--lumina-border-strong)'}`,
          cursor: 'pointer',
          flexShrink: 0,
          transition: 'all var(--duration-fast) var(--ease-out)',
        }}
      >
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '2px',
            left: checked ? 'calc(100% - 18px)' : '2px',
            width: '14px',
            height: '14px',
            borderRadius: '50%',
            background: '#fff',
            transition: 'left var(--duration-fast) var(--ease-out)',
          }}
        />
      </button>
    </div>
  );
}

export function AccessibilityPage() {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState<AccessibilityPreferences>(loadPreferences);

  useEffect(() => {
    savePreferences(prefs);

    // Apply reduced motion to document
    if (prefs.reducedMotion) {
      document.documentElement.style.setProperty('--duration-fast', '0ms');
      document.documentElement.style.setProperty('--duration-normal', '0ms');
      document.documentElement.style.setProperty('--duration-slow', '0ms');
    } else {
      document.documentElement.style.removeProperty('--duration-fast');
      document.documentElement.style.removeProperty('--duration-normal');
      document.documentElement.style.removeProperty('--duration-slow');
    }

    // Apply larger text
    if (prefs.largerText) {
      document.documentElement.style.fontSize = '18px';
    } else {
      document.documentElement.style.fontSize = '16px';
    }

    // Apply high contrast
    if (prefs.highContrast) {
      document.documentElement.classList.add('high-contrast');
    } else {
      document.documentElement.classList.remove('high-contrast');
    }
  }, [prefs]);

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={9}
        title="Accessibility"
        subtitle="Customize how LUMINA looks and feels"
      />

      {/* Persistence Notice */}
      <Card elevated style={{ marginBottom: 'var(--space-6)', borderLeft: '3px solid var(--lumina-system)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-system)',
          marginBottom: 'var(--space-2)',
        }}>
          Storage
        </div>
        <p style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          lineHeight: 'var(--leading-relaxed)',
        }}>
          Preferences are stored locally in your browser. They are not synced to the server
          and will be lost if you clear browser data.
        </p>
      </Card>

      {/* Preferences */}
      <Card>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-2)',
        }}>
          Preferences
        </div>

        <ToggleRow
          label="Reduce Motion"
          description="Minimize animations and transitions. Essential state information remains visible."
          checked={prefs.reducedMotion}
          onChange={(v) => setPrefs({ ...prefs, reducedMotion: v })}
        />

        <ToggleRow
          label="Larger Text"
          description="Increase the base font size for better readability."
          checked={prefs.largerText}
          onChange={(v) => setPrefs({ ...prefs, largerText: v })}
        />

        <ToggleRow
          label="High Contrast"
          description="Increase contrast between text and background for better visibility."
          checked={prefs.highContrast}
          onChange={(v) => setPrefs({ ...prefs, highContrast: v })}
        />
      </Card>

      {/* Built-in Accessibility */}
      <Card style={{ marginTop: 'var(--space-4)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-text-muted)',
          marginBottom: 'var(--space-3)',
        }}>
          Built-in Accessibility
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {[
            'Semantic HTML landmarks (main, nav, header)',
            'Keyboard navigation throughout',
            'Visible focus indicators on all interactive elements',
            'Screen-reader labels on status and interactive elements',
            'Color-independent status communication',
            'prefers-reduced-motion respected by default',
            'Sufficient contrast ratios in design tokens',
          ].map((feature) => (
            <div key={feature} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              fontSize: 'var(--text-xs)',
              color: 'var(--lumina-text-secondary)',
            }}>
              <span aria-hidden="true" style={{ color: 'var(--lumina-recovery)' }}>✓</span>
              {feature}
            </div>
          ))}
        </div>
      </Card>

      <div style={{ marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={() => navigate('/settings')}>
          Back to Settings
        </Button>
      </div>
    </div>
  );
}
