/* ============================================================
   LUMINA Settings Pages Tests
   ============================================================
   Tests for Recovery, Privacy, Accessibility, Security, Settings,
   History pages — covering rendering, empty states, accessibility,
   no fake data, honest capability boundaries.
   ============================================================ */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RecoveryPage } from '@/app/RecoveryPage';
import { PrivacyCenterPage } from '@/app/PrivacyCenterPage';
import { AccessibilityPage } from '@/app/AccessibilityPage';
import { SecurityPage } from '@/app/SecurityPage';
import { SettingsPage } from '@/app/SettingsPage';
import { HistoryPage } from '@/app/HistoryPage';
import {
  getPrivacyPolicy,
  getMyAccount,
  deleteAccount,
} from '@/lib/api/account';

vi.mock('@/hooks/useSessionState', () => ({
  useSessionState: vi.fn(),
}));

vi.mock('@/lib/api/account', () => ({
  getPrivacyPolicy: vi.fn(),
  getMyAccount: vi.fn(),
  deleteAccount: vi.fn(),
}));

import { useSessionState } from '@/hooks/useSessionState';
const mockUseSessionState = vi.mocked(useSessionState);

const mockCredentials = { deviceId: 'test-device-1234abcd', deviceSecret: 'test-secret' };

function renderWithRouter(component: React.ReactNode, path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      {component}
    </MemoryRouter>,
  );
}

// ============================================================
// RECOVERY PAGE
// ============================================================
describe('RecoveryPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows no session state when idle', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    expect(screen.getByText(/no active session/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start session/i })).toBeInTheDocument();
  });

  it('shows loading state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'loading', credentials: mockCredentials, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows unavailable state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'unavailable', credentials: null, session: null, decision: null,
      error: 'Network error', errorCode: 0,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });

  it('renders session summary with real data', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials,
      session: { sessionId: 'sess-001', startedAt: '2026-09-03T10:00:00Z', events: [], evidence: [] },
      decision: {
        state: 'VERIFY', stateLabel: 'Verify',
        reasonCodes: ['authority claim'],
        recommendedAction: 'Verify independently.',
        evidenceCount: 2,
        missingInformation: [],
        observations: ['AUTHORITY_CLAIM'],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    expect(screen.getByText(/session summary/i)).toBeInTheDocument();
    expect(screen.getByText(/recommended next steps/i)).toBeInTheDocument();
    // Observation appears as "Authority Claim" pill and as reason code
    const matches = screen.getAllByText(/authority claim/i);
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  it('shows next steps for money-related observations', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials,
      session: { sessionId: 'sess-001', startedAt: '2026-09-03T10:00:00Z', events: [], evidence: [] },
      decision: {
        state: 'PAUSE', stateLabel: 'Pause',
        reasonCodes: ['money requested'],
        recommendedAction: 'Do not send money.',
        evidenceCount: 3,
        missingInformation: [],
        observations: ['MONEY_REQUEST'],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: false,
        highRiskActions: [{ action: 'SEND_MONEY', status: 'REQUESTED', description: 'test', urgency: 'IMMEDIATE' }],
      },
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    // "Contact your bank" appears in both title and description
    const bankMatches = screen.getAllByText(/contact your bank/i);
    expect(bankMatches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/document what happened/i)).toBeInTheDocument();
  });

  it('does not show fake recovery claims', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<RecoveryPage />);
    expect(screen.queryByText(/you were protected/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/money recovered/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/scam blocked/i)).not.toBeInTheDocument();
  });
});

// ============================================================
// PRIVACY CENTER
// ============================================================
describe('PrivacyCenterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const mockPolicy = {
      retention_policy: {},
      retention_enforcement: 'NOT_IMPLEMENTED',
      summary: {
        what_lumina_stores: ['Phone number (account identity)', 'Incidents and evidence (safety continuity)'],
        what_lumina_does_not_store: ['Location data', 'Contact lists'],
        what_is_shared: ['Sanitized transcript evidence to semantic AI provider'],
        ai_data_boundary: 'AI receives only sanitized evidence. Never phone numbers, OTPs, or raw audio.',
      },
    };
    vi.mocked(getPrivacyPolicy).mockResolvedValue(mockPolicy);
    vi.mocked(getMyAccount).mockResolvedValue({
      user_id: 'user-123', display_name: 'Test', phone_masked: '+91****3210',
      phone_verified: true, emergency_consent: 'GIVEN', account_status: 'ACTIVE',
      created_at: '2026-01-01',
    });
    vi.mocked(deleteAccount).mockResolvedValue({ status: 'ok' });
  });

  it('renders privacy center', () => {
    renderWithRouter(<PrivacyCenterPage />);
    expect(screen.getByRole('heading', { name: /privacy center/i })).toBeInTheDocument();
  });

  it('shows what LUMINA stores and does not store from backend policy', async () => {
    renderWithRouter(<PrivacyCenterPage />);
    expect(await screen.findByText(/phone number \(account identity\)/i)).toBeInTheDocument();
    expect(screen.getByText(/incidents and evidence \(safety continuity\)/i)).toBeInTheDocument();
    expect(screen.getByText(/location data/i)).toBeInTheDocument();
    expect(screen.getByText(/contact lists/i)).toBeInTheDocument();
  });

  it('shows the AI data boundary honestly', async () => {
    renderWithRouter(<PrivacyCenterPage />);
    expect(await screen.findByText(/ai receives only sanitized evidence/i)).toBeInTheDocument();
  });

  it('does not silently fall back to a fabricated policy when the backend fails', async () => {
    vi.mocked(getPrivacyPolicy).mockRejectedValue(new Error('network down'));
    vi.mocked(getMyAccount).mockRejectedValue(new Error('network down'));
    renderWithRouter(<PrivacyCenterPage />);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    // Error surfaced honestly; no fabricated policy content rendered.
    expect(screen.queryByText(/what lumina stores/i)).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/could not load/i);
  });
});

// ============================================================
// ACCESSIBILITY PAGE
// ============================================================
describe('AccessibilityPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.style.removeProperty('font-size');
    document.documentElement.classList.remove('high-contrast');
  });

  it('renders accessibility settings', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByRole('heading', { name: /accessibility/i })).toBeInTheDocument();
  });

  it('shows reduce motion toggle', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByRole('switch', { name: /reduce motion/i })).toBeInTheDocument();
  });

  it('shows larger text toggle', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByRole('switch', { name: /larger text/i })).toBeInTheDocument();
  });

  it('shows high contrast toggle', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByRole('switch', { name: /high contrast/i })).toBeInTheDocument();
  });

  it('persists to localStorage', () => {
    renderWithRouter(<AccessibilityPage />);
    const toggle = screen.getByRole('switch', { name: /reduce motion/i });
    toggle.click();
    expect(localStorage.getItem('lumina_accessibility')).toContain('reducedMotion');
  });

  it('shows built-in accessibility features', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByText(/semantic html landmarks/i)).toBeInTheDocument();
    expect(screen.getByText(/keyboard navigation/i)).toBeInTheDocument();
    expect(screen.getByText(/visible focus indicators/i)).toBeInTheDocument();
  });

  it('shows storage notice', () => {
    renderWithRouter(<AccessibilityPage />);
    expect(screen.getByText(/stored locally/i)).toBeInTheDocument();
    expect(screen.getByText(/not synced to the server/i)).toBeInTheDocument();
  });
});

// ============================================================
// SECURITY PAGE
// ============================================================
describe('SecurityPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders security settings', () => {
    renderWithRouter(<SecurityPage />);
    expect(screen.getByRole('heading', { name: /security/i })).toBeInTheDocument();
  });

  it('shows security features with honest status', () => {
    renderWithRouter(<SecurityPage />);
    expect(screen.getByText(/device-bound authentication/i)).toBeInTheDocument();
    expect(screen.getByText(/hmac request signing/i)).toBeInTheDocument();
    expect(screen.getByText(/credential rotation/i)).toBeInTheDocument();
    const notImpl = screen.getAllByText(/not implemented/i);
    expect(notImpl.length).toBeGreaterThanOrEqual(1);
  });

  it('never renders device secret value', () => {
    renderWithRouter(<SecurityPage />);
    // The mock secret is 'test-secret' — must never appear anywhere
    expect(screen.queryByText('test-secret')).not.toBeInTheDocument();
    expect(screen.queryByText(/test-secret/)).not.toBeInTheDocument();
  });

  it('never renders device secret substrings', () => {
    renderWithRouter(<SecurityPage />);
    // Common substring patterns that could leak secret parts
    expect(screen.queryByText('test-sec')).not.toBeInTheDocument();
    expect(screen.queryByText('est-secret')).not.toBeInTheDocument();
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('never renders device ID value', () => {
    renderWithRouter(<SecurityPage />);
    // The mock device ID must never appear
    expect(screen.queryByText('test-device-1234abcd')).not.toBeInTheDocument();
    expect(screen.queryByText(/test-device/)).not.toBeInTheDocument();
    expect(screen.queryByText(/1234abcd/)).not.toBeInTheDocument();
  });

  it('shows honest credential status (stored securely or not available)', () => {
    renderWithRouter(<SecurityPage />);
    // Without localStorage, shows 'Not Available'; with it, shows 'Stored Securely'
    const hasStored = localStorage.getItem('lumina_device_id') !== null;
    if (hasStored) {
      expect(screen.getByText(/stored securely/i)).toBeInTheDocument();
    } else {
      expect(screen.getByText(/not available/i)).toBeInTheDocument();
    }
  });

  it('shows device identity management', () => {
    renderWithRouter(<SecurityPage />);
    const deviceIdItems = screen.getAllByText(/device identity/i);
    expect(deviceIdItems.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: /clear device/i })).toBeInTheDocument();
  });

  it('shows security notes', () => {
    renderWithRouter(<SecurityPage />);
    expect(screen.getByText(/never transmitted to the server/i)).toBeInTheDocument();
    expect(screen.getByText(/replay attacks/i)).toBeInTheDocument();
  });

  it('does not render raw authentication material', () => {
    renderWithRouter(<SecurityPage />);
    const body = document.body.textContent || '';
    // Must not contain any hex strings that could be signatures
    expect(body).not.toMatch(/[0-9a-f]{64}/);
    // Must not contain base64-like strings
    expect(body).not.toMatch(/[A-Za-z0-9+/]{40,}={0,2}/);
  });
});

// ============================================================
// SETTINGS PAGE
// ============================================================
describe('SettingsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders settings hub', () => {
    renderWithRouter(<SettingsPage />);
    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
  });

  it('shows all settings sections', () => {
    renderWithRouter(<SettingsPage />);
    // Use headings for section labels to disambiguate from button text
    expect(screen.getByRole('heading', { name: 'Safety' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Privacy' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Accessibility' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Security' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'About' })).toBeInTheDocument();
  });

  it('shows product description', () => {
    renderWithRouter(<SettingsPage />);
    expect(screen.getByText(/evidence-driven personal safety/i)).toBeInTheDocument();
  });

  it('does not claim unsupported capabilities', () => {
    renderWithRouter(<SettingsPage />);
    expect(screen.queryByText(/ai detects every scam/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/military-grade/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/100% accurate/i)).not.toBeInTheDocument();
  });
});

// ============================================================
// HISTORY PAGE
// ============================================================
describe('HistoryPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders history page with honest empty state', () => {
    renderWithRouter(<HistoryPage />);
    expect(screen.getByRole('heading', { name: /case history/i })).toBeInTheDocument();
    expect(screen.getByText(/no history available/i)).toBeInTheDocument();
    expect(screen.getByText(/not available yet/i)).toBeInTheDocument();
  });

  it('explains what will be here', () => {
    renderWithRouter(<HistoryPage />);
    expect(screen.getByText(/what will be here/i)).toBeInTheDocument();
    // "session listing endpoint" appears in both empty state and info card
    const matches = screen.getAllByText(/session listing endpoint/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('does not show fake history entries', () => {
    renderWithRouter(<HistoryPage />);
    expect(screen.queryByText(/case-\d+/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/incident/i)).not.toBeInTheDocument();
  });
});
