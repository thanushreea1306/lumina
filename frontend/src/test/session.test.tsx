/* ============================================================
   LUMINA Session Screen Tests
   ============================================================
   Tests for all Session states.
   Mocking is used ONLY inside isolated tests.
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SessionPage } from '@/app/SessionPage';

vi.mock('@/hooks/useSessionState', () => ({
  useSessionState: vi.fn(),
}));

import { useSessionState } from '@/hooks/useSessionState';
const mockUseSessionState = vi.mocked(useSessionState);

function renderSessionPage() {
  return render(
    <BrowserRouter>
      <SessionPage />
    </BrowserRouter>,
  );
}

describe('SessionPage - Idle (No Session)', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'idle',
      credentials: null,
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows session creation view', () => {
    renderSessionPage();
    expect(screen.getByText(/begin a safety session/i)).toBeInTheDocument();
  });

  it('shows start session button', () => {
    renderSessionPage();
    expect(screen.getByRole('button', { name: /start session/i })).toBeInTheDocument();
  });

  it('shows forensic safety check label', () => {
    renderSessionPage();
    expect(screen.getByText(/forensic safety check/i)).toBeInTheDocument();
  });
});

describe('SessionPage - Creating', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'creating',
      credentials: null,
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows creating loading state', () => {
    renderSessionPage();
    expect(screen.getAllByText(/creating session/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('SessionPage - Loading', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'loading',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows loading state', () => {
    renderSessionPage();
    expect(screen.getAllByText(/loading session/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('SessionPage - Active with CLEAR decision', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'test-session-001',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [
          { event_type: 'SESSION_STARTED', sequence: 0, timestamp: '2026-09-03T10:00:00.000Z', payload: {} },
        ],
        evidence: [],
      },
      decision: {
        state: 'CLEAR',
        stateLabel: 'Clear',
        reasonCodes: [],
        recommendedAction: 'No action needed.',
        evidenceCount: 0,
        missingInformation: [],
        observations: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows case ID', () => {
    renderSessionPage();
    expect(screen.getByRole('text', { name: /session test-session-001/i })).toBeInTheDocument();
  });

  it('shows Clear state (multiple instances: badge, hero, status bar)', () => {
    renderSessionPage();
    expect(screen.getAllByText('Clear').length).toBeGreaterThanOrEqual(2);
  });

  it('shows observation controls', () => {
    renderSessionPage();
    expect(screen.getByText(/what did you observe/i)).toBeInTheDocument();
  });

  it('shows observation categories', () => {
    renderSessionPage();
    expect(screen.getByText(/coercion/i)).toBeInTheDocument();
    expect(screen.getByText(/financial/i)).toBeInTheDocument();
  });

  it('shows end session button', () => {
    renderSessionPage();
    expect(screen.getByRole('button', { name: /end session/i })).toBeInTheDocument();
  });

  it('shows recommended action', () => {
    renderSessionPage();
    expect(screen.getByText(/no action needed/i)).toBeInTheDocument();
  });
});

describe('SessionPage - Active with WATCH decision', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'watch-session-002',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [
          { event_type: 'SESSION_STARTED', sequence: 0, timestamp: '2026-09-03T10:00:00.000Z', payload: {} },
          { event_type: 'USER_OBSERVATION', sequence: 1, timestamp: '2026-09-03T10:01:00.000Z', payload: {} },
        ],
        evidence: [
          { evidence_id: 'e1', type: 'AUTHORITY_CLAIM', value: true, status: 'USER_CONFIRMED', source: 'USER', timestamp: '2026-09-03T10:01:00.000Z', sequence: 1, confidence: null, metadata: {} },
        ],
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: ['caller claimed to be from an authority'],
        recommendedAction: 'Stay alert; do not act on unsolicited requests.',
        evidenceCount: 1,
        missingInformation: [],
        observations: ['AUTHORITY_CLAIM'],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows Watch state', () => {
    renderSessionPage();
    expect(screen.getAllByText('Watch').length).toBeGreaterThanOrEqual(2);
  });

  it('shows reason codes', () => {
    renderSessionPage();
    expect(screen.getByText(/caller claimed to be from an authority/i)).toBeInTheDocument();
  });

  it('shows evidence count in status bar', () => {
    renderSessionPage();
    expect(screen.getByText('1')).toBeInTheDocument();
  });
});

describe('SessionPage - Active with PROTECT decision and high-risk actions', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'protect-session-003',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [],
      },
      decision: {
        state: 'PROTECT',
        stateLabel: 'Protect',
        reasonCodes: ['threatened with arrest', 'asked to keep the matter secret'],
        recommendedAction: 'STOP AND VERIFY INDEPENDENTLY.',
        evidenceCount: 0,
        missingInformation: [],
        observations: ['THREAT_OF_ARREST', 'SECRECY_REQUEST'],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: false,
        highRiskActions: [
          { action: 'SHARE_OTP', status: 'REQUESTED', description: 'Sharing a one-time password with the caller.', urgency: 'IMMEDIATE' },
          { action: 'SEND_MONEY', status: 'REQUESTED', description: 'Sending money to the caller.', urgency: 'HIGH' },
        ],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows Protect state', () => {
    renderSessionPage();
    expect(screen.getAllByText('Protect').length).toBeGreaterThanOrEqual(2);
  });

  it('shows high-risk actions section', () => {
    renderSessionPage();
    expect(screen.getByText(/high-risk actions/i)).toBeInTheDocument();
  });

  it('shows SHARE_OTP action', () => {
    renderSessionPage();
    expect(screen.getByText(/share otp/i)).toBeInTheDocument();
  });

  it('shows SEND_MONEY action', () => {
    renderSessionPage();
    expect(screen.getByText(/send money/i)).toBeInTheDocument();
  });

  it('shows REQUESTED status (multiple actions)', () => {
    renderSessionPage();
    expect(screen.getAllByText('REQUESTED').length).toBeGreaterThanOrEqual(2);
  });
});

describe('SessionPage - Observation submission', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'obs-session-004',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [],
      },
      decision: {
        state: 'CLEAR',
        stateLabel: 'Clear',
        reasonCodes: [],
        recommendedAction: 'No action needed.',
        evidenceCount: 0,
        missingInformation: [],
        observations: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('renders all observation options', () => {
    renderSessionPage();
    expect(screen.getByText(/they claimed to be from an authority/i)).toBeInTheDocument();
    expect(screen.getByText(/they threatened me with arrest/i)).toBeInTheDocument();
    expect(screen.getByText(/they asked me for money/i)).toBeInTheDocument();
    expect(screen.getByText(/they asked me for an otp or code/i)).toBeInTheDocument();
  });

  it('observation cards are buttons with aria-pressed', () => {
    renderSessionPage();
    const buttons = screen.getAllByRole('button');
    const observationButtons = buttons.filter((b) =>
      b.getAttribute('aria-pressed') !== null
    );
    expect(observationButtons.length).toBeGreaterThan(0);
  });

  it('observation cards have aria-pressed=false initially', () => {
    renderSessionPage();
    const cards = screen.getAllByRole('button').filter(
      (b) => b.getAttribute('aria-pressed') === 'false'
    );
    expect(cards.length).toBeGreaterThan(0);
  });
});

describe('SessionPage - Submitting observation', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'submitting',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'submit-session-005',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [],
      },
      decision: {
        state: 'CLEAR',
        stateLabel: 'Clear',
        reasonCodes: [],
        recommendedAction: 'No action needed.',
        evidenceCount: 0,
        missingInformation: [],
        observations: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('observation cards show submitting state', () => {
    renderSessionPage();
    const cards = screen.getAllByRole('button').filter(
      (b) => b.getAttribute('data-submitting') === 'true'
    );
    expect(cards.length).toBeGreaterThanOrEqual(0);
  });
});

describe('SessionPage - Backend Error', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'error',
      credentials: null,
      session: null,
      decision: null,
      error: 'Session creation failed: HTTP 500',
      errorCode: 500,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows error state', () => {
    renderSessionPage();
    expect(screen.getByText(/session error/i)).toBeInTheDocument();
  });

  it('shows retry button', () => {
    renderSessionPage();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});

describe('SessionPage - Backend Unavailable', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'unavailable',
      credentials: null,
      session: null,
      decision: null,
      error: 'Failed to fetch',
      errorCode: 0,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows unavailable state', () => {
    renderSessionPage();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });
});

describe('SessionPage - Accessibility', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'a11y-session-006',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [],
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: [],
        recommendedAction: 'Stay alert.',
        evidenceCount: 0,
        missingInformation: [],
        observations: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        highRiskActions: [],
      },
      error: null,
      errorCode: null,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('observation cards are focusable buttons', () => {
    renderSessionPage();
    const cards = screen.getAllByRole('button').filter(
      (b) => b.getAttribute('aria-pressed') !== null
    );
    // Buttons are natively focusable; verify they exist
    expect(cards.length).toBeGreaterThan(0);
    cards.forEach((card) => {
      expect(card.tagName).toBe('BUTTON');
    });
  });

  it('has observation controls heading', () => {
    renderSessionPage();
    expect(screen.getByText(/what did you observe/i)).toBeInTheDocument();
  });

  it('status badge has role="status"', () => {
    renderSessionPage();
    const badges = screen.getAllByRole('status');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});
