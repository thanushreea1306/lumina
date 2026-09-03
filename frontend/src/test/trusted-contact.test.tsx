/* ============================================================
   LUMINA Trusted Contact Tests
   ============================================================
   Tests for the Trusted Contact experience:
   - Not configured state
   - Session context
   - Alert sending
   - Delivery status
   - Error handling
   - Data minimization
   - Accessibility
   - No fake contacts/delivery
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TrustedContactPage } from '@/app/TrustedContactPage';

vi.mock('@/hooks/useSessionState', () => ({
  useSessionState: vi.fn(),
}));

vi.mock('@/lib/api/alert', () => ({
  sendAlert: vi.fn(),
}));

import { useSessionState } from '@/hooks/useSessionState';
import { sendAlert } from '@/lib/api/alert';
const mockUseSessionState = vi.mocked(useSessionState);
const mockSendAlert = vi.mocked(sendAlert);

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
  reasonCodes: ['authority claim'],
  recommendedAction: 'Verify independently.',
  evidenceCount: 2,
  missingInformation: [],
  observations: ['AUTHORITY_CLAIM'],
  hasRequestedHighRiskAction: false,
  hasPerformedHighRiskAction: false,
  highRiskActions: [],
};

function renderWithRouter(component: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={['/trusted-contact']}>
      {component}
    </MemoryRouter>,
  );
}

describe('TrustedContactPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the trusted contact heading', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    // Use heading role to disambiguate from capability banner text
    expect(screen.getByRole('heading', { name: 'Trusted Contact' })).toBeInTheDocument();
  });

  it('shows capability notice', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByText(/not yet fully configured/i)).toBeInTheDocument();
  });

  it('shows data minimization notice', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByText(/data minimization/i)).toBeInTheDocument();
    expect(screen.getByText(/does not automatically share/i)).toBeInTheDocument();
  });

  it('shows no session message when idle', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByText(/no active session/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start session/i })).toBeInTheDocument();
  });

  it('shows session context when active', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByText(/current session/i)).toBeInTheDocument();
    // Use the specific state text to disambiguate
    expect(screen.getByText(/state:/i)).toBeInTheDocument();
  });

  it('shows send alert button', () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByRole('button', { name: /send alert/i })).toBeInTheDocument();
  });

  it('sends alert and shows NO_RECIPIENT status', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockSendAlert.mockResolvedValue({
      ok: true,
      data: {
        status: 'NOT_CONFIGURED',
        alert_sent: false,
        delivered: false,
        delivery_status: 'NO_RECIPIENT',
        message: 'No elder/recipient name was provided; no alert was attempted.',
        reason: 'no named recipient configured',
      },
    });
    renderWithRouter(<TrustedContactPage />);
    
    fireEvent.click(screen.getByRole('button', { name: /send alert/i }));
    
    await waitFor(() => {
      expect(mockSendAlert).toHaveBeenCalledWith(
        mockCredentials,
        expect.objectContaining({ elder_name: 'current_user' }),
      );
    });

    await waitFor(() => {
      // The DeliveryStatusDisplay shows "No Recipient" label
      expect(screen.getByText(/no recipient/i)).toBeInTheDocument();
      expect(screen.getByText(/no elder\/recipient name/i)).toBeInTheDocument();
    });
  });

  it('shows NOT_CONFIGURED delivery status honestly', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockSendAlert.mockResolvedValue({
      ok: true,
      data: {
        status: 'NOT_CONFIGURED',
        alert_sent: false,
        delivered: false,
        delivery_status: 'NO_RECIPIENT',
        message: 'No elder/recipient name was provided; no alert was attempted.',
        reason: 'no named recipient configured',
      },
    });
    renderWithRouter(<TrustedContactPage />);
    
    fireEvent.click(screen.getByRole('button', { name: /send alert/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/no recipient/i)).toBeInTheDocument();
    });
    // Must NOT show fake success
    expect(screen.queryByText(/alert sent successfully/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/delivered/i)).not.toBeInTheDocument();
  });

  it('shows alert error on failure', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockSendAlert.mockResolvedValue({ ok: false, status: 500, error: 'Server error' });
    renderWithRouter(<TrustedContactPage />);
    
    fireEvent.click(screen.getByRole('button', { name: /send alert/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });
  });

  it('shows loading state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'loading', credentials: mockCredentials, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows unavailable state', () => {
    mockUseSessionState.mockReturnValue({
      status: 'unavailable', credentials: null, session: null, decision: null,
      error: 'Network error', errorCode: 0,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });

  it('shows how it works steps', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    expect(screen.getByRole('list', { name: /how alerts work/i })).toBeInTheDocument();
    expect(screen.getByText(/review what information/i)).toBeInTheDocument();
    expect(screen.getByText(/explicitly confirm/i)).toBeInTheDocument();
  });

  it('does not show fake contacts or delivery success', () => {
    mockUseSessionState.mockReturnValue({
      status: 'idle', credentials: null, session: null, decision: null,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    renderWithRouter(<TrustedContactPage />);
    // No fake contacts
    expect(screen.queryByText(/mom/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/dad/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/friend/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/emergency contact/i)).not.toBeInTheDocument();
  });

  it('has accessible alert status', async () => {
    mockUseSessionState.mockReturnValue({
      status: 'active', credentials: mockCredentials, session: mockSession,
      decision: mockDecision,
      error: null, errorCode: null,
      startNewSession: vi.fn(), submitObservation: vi.fn(), submitEvent: vi.fn(),
      refresh: vi.fn(), endSession: vi.fn(),
    });
    mockSendAlert.mockResolvedValue({
      ok: true,
      data: {
        status: 'NOT_CONFIGURED',
        alert_sent: false,
        delivered: false,
        delivery_status: 'NO_RECIPIENT',
        message: 'No recipient.',
        reason: 'no named recipient configured',
      },
    });
    renderWithRouter(<TrustedContactPage />);
    
    fireEvent.click(screen.getByRole('button', { name: /send alert/i }));
    
    await waitFor(() => {
      const status = screen.getByRole('status');
      expect(status).toHaveAttribute('aria-live', 'polite');
    });
  });
});
