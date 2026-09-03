/* ============================================================
   LUMINA Intervention Tests
   ============================================================
   Tests for VERIFY, PAUSE, PROTECT interventions:
   - Rendering with real decision data
   - Reason codes
   - Recommended action
   - High-risk actions
   - Missing information
   - User responses
   - Response submission
   - Backend errors
   - Unavailable decision
   - No active session
   - Accessibility
   - No fake risk/confidence
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { VerifyPage } from '@/app/VerifyPage';
import { PausePage } from '@/app/PausePage';
import { ProtectPage } from '@/app/ProtectPage';

vi.mock('@/hooks/useSessionState', () => ({
  useSessionState: vi.fn(),
}));

vi.mock('@/lib/api/sessions', () => ({
  userResponse: vi.fn(),
}));

import { useSessionState } from '@/hooks/useSessionState';
import { userResponse } from '@/lib/api/sessions';
const mockUseSessionState = vi.mocked(useSessionState);
const mockUserResponse = vi.mocked(userResponse);

// ---- Shared mock data ----
const mockCredentials = { deviceId: 'test-device', deviceSecret: 'test-secret' };

const mockSession = {
  sessionId: 'test-session-001',
  startedAt: '2026-09-03T10:00:00.000Z',
  events: [],
  evidence: [],
};

const mockDecision = {
  state: 'VERIFY' as const,
  stateLabel: 'Verify',
  reasonCodes: ['caller claimed to be from an authority', 'asked for an OTP/code'],
  recommendedAction: 'Verify the caller independently using an official contact method.',
  evidenceCount: 2,
  missingInformation: ['caller identity not confirmed'],
  observations: ['AUTHORITY_CLAIM', 'OTP_REQUEST'],
  hasRequestedHighRiskAction: true,
  hasPerformedHighRiskAction: false,
  highRiskActions: [
    { action: 'SHARE_OTP', status: 'REQUESTED', description: 'Caller asked for OTP', urgency: 'HIGH' },
  ],
};

function renderWithRouter(component: React.ReactNode, initialEntries = ['/verify']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {component}
    </MemoryRouter>,
  );
}

// ============================================================
// VERIFY
// ============================================================

describe('VerifyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows no session state when idle', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByText(/no active safety session/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /go to session/i })).toBeInTheDocument();
  });

  it('shows loading state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'loading', credentials: mockCredentials, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getAllByText(/loading/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows error state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'error', credentials: null, session: null, decision: null,
      error: 'HTTP 500', errorCode: 500,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('shows unavailable state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'unavailable', credentials: null, session: null, decision: null,
      error: 'Network error', errorCode: 0,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });

  it('renders VERIFY intervention with decision data', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByRole('status', { name: /safety status/i })).toBeInTheDocument();
    // Use heading role to disambiguate from StatusBadge
    expect(screen.getByRole('heading', { name: 'Verify' })).toBeInTheDocument();
    // Subtitle contains 'Verify the caller' — use the subtitle class to disambiguate
    expect(document.querySelector('.intervention-subtitle')?.textContent).toContain('Verify the caller');
  });

  it('displays reason codes', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByText(/caller claimed to be from an authority/i)).toBeInTheDocument();
    expect(screen.getByText(/asked for an otp\/code/i)).toBeInTheDocument();
  });

  it('displays recommended action', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByText(/verify the caller independently/i)).toBeInTheDocument();
  });

  it('displays high-risk actions', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    // Use the high-risk list container to disambiguate
    const highRiskList = screen.getByRole('list', { name: /high-risk actions/i });
    expect(highRiskList).toBeInTheDocument();
    expect(screen.getByText(/caller asked for otp/i)).toBeInTheDocument();
  });

  it('displays missing information', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByText(/caller identity not confirmed/i)).toBeInTheDocument();
  });

  it('shows response options', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByRole('button', { name: /it's legitimate/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cannot verify right now/i })).toBeInTheDocument();
  });

  it('submits user response', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockUserResponse.mockResolvedValue({ ok: true, data: {} as never });
    renderWithRouter(<VerifyPage />, ['/verify']);
    
    fireEvent.click(screen.getByRole('button', { name: /it's legitimate/i }));
    
    await waitFor(() => {
      expect(mockUserResponse).toHaveBeenCalledWith(
        mockCredentials, 'test-session-001',
        { action: 'verification_completed', response: 'verified_safe' }
      );
    });
    
    await waitFor(() => {
      expect(screen.getByText(/response recorded/i)).toBeInTheDocument();
    });
  });

  it('shows error on response failure', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockUserResponse.mockResolvedValue({ ok: false, status: 500, error: 'Server error' });
    renderWithRouter(<VerifyPage />, ['/verify']);
    
    fireEvent.click(screen.getByRole('button', { name: /it's legitimate/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });
  });

  it('shows safety guidance', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    // The subtitle and guidance both mention 'verify the caller' — use guidance list
    const guidanceList = screen.getByRole('list', { name: /what you should do/i });
    expect(guidanceList).toBeInTheDocument();
    expect(screen.getByText(/do not use phone numbers, links, or details provided by the caller/i)).toBeInTheDocument();
  });

  it('does not display fake risk scores or confidence', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.queryByText(/risk score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/i)).not.toBeInTheDocument();
  });

  it('has accessible intervention status', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    const status = screen.getByRole('status', { name: /safety status/i });
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('Verify'));
  });

  it('renders reason list with accessible label', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    expect(screen.getByRole('list', { name: /reasons for current safety state/i })).toBeInTheDocument();
  });
});

// ============================================================
// PAUSE
// ============================================================

describe('PausePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const pauseDecision = {
    ...mockDecision,
    state: 'PAUSE' as const,
    stateLabel: 'Pause',
    reasonCodes: ['asked for money transfer', 'created urgency'],
    recommendedAction: 'Do not share codes, passwords, or money. Pause and verify.',
    highRiskActions: [
      { action: 'SEND_MONEY', status: 'REQUESTED', description: 'Caller asked for money transfer', urgency: 'IMMEDIATE' },
    ],
  };

  it('renders PAUSE intervention with decision data', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    expect(screen.getByRole('status', { name: /safety status/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pause' })).toBeInTheDocument();
    expect(screen.getByText(/something in this interaction requires caution/i)).toBeInTheDocument();
  });

  it('shows protection guidance', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    expect(screen.getByText(/stop what you are doing/i)).toBeInTheDocument();
    expect(screen.getByText(/do not share any codes, passwords/i)).toBeInTheDocument();
  });

  it('shows capability note', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    // Use the container class to disambiguate
    const capabilityNote = document.querySelector('.capability-note');
    expect(capabilityNote).toBeInTheDocument();
    expect(capabilityNote?.textContent).toContain('cannot block');
  });

  it('shows response options', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    expect(screen.getByRole('button', { name: /stopped the interaction/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /understand the risk but will proceed/i })).toBeInTheDocument();
  });

  it('submits pause response', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockUserResponse.mockResolvedValue({ ok: true, data: {} as never });
    renderWithRouter(<PausePage />, ['/pause']);
    
    fireEvent.click(screen.getByRole('button', { name: /stopped the interaction/i }));
    
    await waitFor(() => {
      expect(mockUserResponse).toHaveBeenCalledWith(
        mockCredentials, 'test-session-001',
        { action: 'pause_decision', response: 'stopped_interaction' }
      );
    });
    
    await waitFor(() => {
      expect(screen.getByText(/response recorded/i)).toBeInTheDocument();
    });
  });

  it('shows no session state when idle', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    expect(screen.getByText(/no active safety session/i)).toBeInTheDocument();
  });

  it('does not display fake risk scores', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: pauseDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<PausePage />, ['/pause']);
    expect(screen.queryByText(/risk score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/scam probability/i)).not.toBeInTheDocument();
  });
});

// ============================================================
// PROTECT
// ============================================================

describe('ProtectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const protectDecision = {
    ...mockDecision,
    state: 'PROTECT' as const,
    stateLabel: 'Protect',
    reasonCodes: ['multiple high-risk indicators', 'money requested', 'OTP requested'],
    recommendedAction: 'Stop the interaction. Do not share any information.',
    hasRequestedHighRiskAction: true,
    hasPerformedHighRiskAction: false,
    highRiskActions: [
      { action: 'SHARE_OTP', status: 'REQUESTED', description: 'Caller asked for OTP', urgency: 'IMMEDIATE' },
      { action: 'SEND_MONEY', status: 'REQUESTED', description: 'Caller asked for money', urgency: 'IMMEDIATE' },
    ],
  };

  it('renders PROTECT intervention with decision data', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByRole('status', { name: /safety status/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Protect' })).toBeInTheDocument();
    expect(screen.getByText(/high-risk indicators are present/i)).toBeInTheDocument();
  });

  it('shows warning banner', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/do not share codes, passwords, money/i)).toBeInTheDocument();
  });

  it('shows protective guidance', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByText(/stop the interaction immediately/i)).toBeInTheDocument();
    expect(screen.getByText(/if you already shared a code or password/i)).toBeInTheDocument();
    expect(screen.getByText(/if you already sent money/i)).toBeInTheDocument();
  });

  it('shows response options', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByRole('button', { name: /stopped and secured/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /need help securing/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /understand the risk but will proceed/i })).toBeInTheDocument();
  });

  it('submits protect response', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockUserResponse.mockResolvedValue({ ok: true, data: {} as never });
    renderWithRouter(<ProtectPage />, ['/protect']);
    
    fireEvent.click(screen.getByRole('button', { name: /stopped and secured/i }));
    
    await waitFor(() => {
      expect(mockUserResponse).toHaveBeenCalledWith(
        mockCredentials, 'test-session-001',
        { action: 'protect_action', response: 'stopped_and_secured' }
      );
    });
    
    await waitFor(() => {
      expect(screen.getByText(/response recorded/i)).toBeInTheDocument();
    });
  });

  it('shows emergency services note', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByText(/contact local emergency services/i)).toBeInTheDocument();
  });

  it('displays multiple high-risk actions', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    const highRiskList = screen.getByRole('list', { name: /high-risk actions/i });
    expect(highRiskList).toBeInTheDocument();
    expect(screen.getByText(/caller asked for otp/i)).toBeInTheDocument();
    expect(screen.getByText(/caller asked for money/i)).toBeInTheDocument();
  });

  it('shows no session state when idle', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByText(/no active safety session/i)).toBeInTheDocument();
  });

  it('shows error state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'error', credentials: null, session: null, decision: null,
      error: 'HTTP 500', errorCode: 500,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('does not display fake risk scores or scam percentages', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: protectDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<ProtectPage />, ['/protect']);
    expect(screen.queryByText(/risk score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/i)).not.toBeInTheDocument();
  });
});

// ============================================================
// Shared Intervention Component Tests
// ============================================================

describe('Intervention Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ResponseOptions handles keyboard navigation', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<VerifyPage />, ['/verify']);
    const responseGroup = screen.getByRole('group', { name: /available responses/i });
    const buttons = responseGroup.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThan(0);
    buttons.forEach((btn) => {
      expect(btn).not.toHaveAttribute('tabindex', '-1');
    });
  });

  it('ResponseOptions disables buttons while submitting', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockUserResponse.mockImplementation(() => new Promise(() => {})); // Never resolves
    renderWithRouter(<VerifyPage />, ['/verify']);
    
    fireEvent.click(screen.getByRole('button', { name: /it's legitimate/i }));
    
    await waitFor(() => {
      const responseGroup = screen.getByRole('group', { name: /available responses/i });
      const buttons = responseGroup.querySelectorAll('button');
      buttons.forEach((btn) => {
        expect(btn).toBeDisabled();
      });
    });
  });
});
