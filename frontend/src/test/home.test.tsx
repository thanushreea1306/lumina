/* ============================================================
   LUMINA Home Screen Tests
   ============================================================
   Tests for all Home screen states.
   Mocking is used ONLY inside isolated tests.
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { HomePage } from '@/app/HomePage';

// ---- Mock the API layer ----
vi.mock('@/hooks/useHomeState', () => ({
  useHomeState: vi.fn(),
}));

import { useHomeState } from '@/hooks/useHomeState';
const mockUseHomeState = vi.mocked(useHomeState);

function renderHomePage() {
  return render(
    <BrowserRouter>
      <HomePage />
    </BrowserRouter>,
  );
}

describe('HomePage - Loading State', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'loading',
      credentials: null,
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows loading state', () => {
    renderHomePage();
    expect(screen.getAllByText(/connecting to lumina/i).length).toBeGreaterThanOrEqual(1);
  });

  it('has role="status" for screen readers', () => {
    renderHomePage();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('HomePage - No Active Session', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'no_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows "All Clear" status', () => {
    renderHomePage();
    expect(screen.getByText(/all clear/i)).toBeInTheDocument();
  });

  it('shows calm message', () => {
    renderHomePage();
    expect(screen.getByText(/nothing requires your attention/i)).toBeInTheDocument();
  });

  it('shows evidence-driven description', () => {
    renderHomePage();
    expect(screen.getByText(/evidence/i)).toBeInTheDocument();
  });

  it('shows recent activity section with unavailable state', () => {
    renderHomePage();
    expect(screen.getByText(/recent activity/i)).toBeInTheDocument();
    expect(screen.getByText(/session history unavailable/i)).toBeInTheDocument();
  });

  it('explains backend limitation honestly', () => {
    renderHomePage();
    expect(screen.getByText(/does not currently expose a session listing endpoint/i)).toBeInTheDocument();
  });

  it('has role="status" on the clear indicator', () => {
    renderHomePage();
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('Clear'));
  });
});

describe('HomePage - Active Session: CLEAR', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'abc123def456',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 3,
        evidenceCount: 2,
      },
      decision: {
        state: 'CLEAR',
        stateLabel: 'Clear',
        reasonCodes: [],
        recommendedAction: 'No action needed.',
        evidenceCount: 2,
        missingInformation: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        observations: [],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows safety assessment heading', () => {
    renderHomePage();
    expect(screen.getByText(/safety assessment/i)).toBeInTheDocument();
  });

  it('shows Clear state label (h1)', () => {
    renderHomePage();
    const headings = screen.getAllByText('Clear');
    // Should appear in h1, badge, and context row
    expect(headings.length).toBeGreaterThanOrEqual(2);
  });

  it('shows recommended action', () => {
    renderHomePage();
    expect(screen.getByText(/no action needed/i)).toBeInTheDocument();
  });

  it('shows evidence count', () => {
    renderHomePage();
    expect(screen.getByText(/2 pieces/i)).toBeInTheDocument();
  });

  it('shows case ID', () => {
    renderHomePage();
    expect(screen.getByRole('text', { name: /session abc123def456/i })).toBeInTheDocument();
  });

  it('shows recent activity section', () => {
    renderHomePage();
    expect(screen.getByText(/recent activity/i)).toBeInTheDocument();
  });

  it('has data-state attribute for CSS styling', () => {
    renderHomePage();
    const hero = document.querySelector('[data-state="CLEAR"]');
    expect(hero).toBeInTheDocument();
  });
});

describe('HomePage - Active Session: WATCH', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'watch-session-001',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 5,
        evidenceCount: 4,
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: ['caller claimed to be from an authority', 'pressed for urgency'],
        recommendedAction: 'Stay alert; do not act on unsolicited requests for money, codes, or access.',
        evidenceCount: 4,
        missingInformation: ['caller_identity unavailable'],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        observations: ['AUTHORITY_CLAIM', 'URGENCY'],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows Watch state', () => {
    renderHomePage();
    const watchElements = screen.getAllByText('Watch');
    expect(watchElements.length).toBeGreaterThanOrEqual(2);
  });

  it('shows reason codes', () => {
    renderHomePage();
    expect(screen.getByText(/caller claimed to be from an authority/i)).toBeInTheDocument();
    expect(screen.getByText(/pressed for urgency/i)).toBeInTheDocument();
  });

  it('shows observations count', () => {
    renderHomePage();
    expect(screen.getByText(/2 observations/i)).toBeInTheDocument();
  });

  it('shows missing information', () => {
    renderHomePage();
    expect(screen.getByText(/1 item not yet available/i)).toBeInTheDocument();
  });

  it('has data-state="WATCH"', () => {
    renderHomePage();
    expect(document.querySelector('[data-state="WATCH"]')).toBeInTheDocument();
  });
});

describe('HomePage - Active Session: VERIFY', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'verify-session-002',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 6,
        evidenceCount: 5,
      },
      decision: {
        state: 'VERIFY',
        stateLabel: 'Verify',
        reasonCodes: ['asked for money'],
        recommendedAction: 'VERIFY INDEPENDENTLY before proceeding with the requested action.',
        evidenceCount: 5,
        missingInformation: [],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: false,
        observations: ['MONEY_REQUEST'],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows Verify state', () => {
    renderHomePage();
    const verifyElements = screen.getAllByText('Verify');
    expect(verifyElements.length).toBeGreaterThanOrEqual(2);
  });

  it('shows action requested indicator', () => {
    renderHomePage();
    expect(screen.getByText(/action requested/i)).toBeInTheDocument();
  });

  it('has data-state="VERIFY"', () => {
    renderHomePage();
    expect(document.querySelector('[data-state="VERIFY"]')).toBeInTheDocument();
  });
});

describe('HomePage - Active Session: PAUSE', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'pause-session-003',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 7,
        evidenceCount: 6,
      },
      decision: {
        state: 'PAUSE',
        stateLabel: 'Pause',
        reasonCodes: ['asked for an OTP/code'],
        recommendedAction: 'PAUSE. Do not share OTPs, passwords, credentials, or send money. Verify independently.',
        evidenceCount: 6,
        missingInformation: [],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: false,
        observations: ['OTP_REQUEST'],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows Pause state', () => {
    renderHomePage();
    const pauseElements = screen.getAllByText('Pause');
    expect(pauseElements.length).toBeGreaterThanOrEqual(2);
  });

  it('shows action requested indicator', () => {
    renderHomePage();
    expect(screen.getByText(/action requested/i)).toBeInTheDocument();
  });

  it('has data-state="PAUSE"', () => {
    renderHomePage();
    expect(document.querySelector('[data-state="PAUSE"]')).toBeInTheDocument();
  });
});

describe('HomePage - Active Session: PROTECT', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'protect-session-004',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 10,
        evidenceCount: 8,
      },
      decision: {
        state: 'PROTECT',
        stateLabel: 'Protect',
        reasonCodes: ['threatened with arrest', 'asked to keep the matter secret', 'asked for money'],
        recommendedAction: 'STOP AND VERIFY INDEPENDENTLY. Do not send money, codes, or grant remote access.',
        evidenceCount: 8,
        missingInformation: [],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: false,
        observations: ['THREAT_OF_ARREST', 'SECRECY_REQUEST', 'MONEY_REQUEST'],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows Protect state', () => {
    renderHomePage();
    const protectElements = screen.getAllByText('Protect');
    expect(protectElements.length).toBeGreaterThanOrEqual(2);
  });

  it('shows multiple reason codes', () => {
    renderHomePage();
    expect(screen.getByText(/threatened with arrest/i)).toBeInTheDocument();
    expect(screen.getByText(/asked to keep the matter secret/i)).toBeInTheDocument();
    expect(screen.getByText(/asked for money/i)).toBeInTheDocument();
  });

  it('shows 3 observations', () => {
    renderHomePage();
    expect(screen.getByText(/3 observations/i)).toBeInTheDocument();
  });

  it('has data-state="PROTECT"', () => {
    renderHomePage();
    expect(document.querySelector('[data-state="PROTECT"]')).toBeInTheDocument();
  });
});

describe('HomePage - Active Session: RECOVERY', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'recovery-session-005',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 12,
        evidenceCount: 10,
      },
      decision: {
        state: 'RECOVERY',
        stateLabel: 'Recovery',
        reasonCodes: ['a high-risk action was already performed'],
        recommendedAction: 'SECURE YOUR ACCOUNTS NOW. Change passwords, contact the bank directly.',
        evidenceCount: 10,
        missingInformation: [],
        hasRequestedHighRiskAction: true,
        hasPerformedHighRiskAction: true,
        observations: ['OTP_REQUEST', 'MONEY_REQUEST'],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows Recovery state', () => {
    renderHomePage();
    const recoveryElements = screen.getAllByText('Recovery');
    expect(recoveryElements.length).toBeGreaterThanOrEqual(2);
  });

  it('shows action performed indicator', () => {
    renderHomePage();
    expect(screen.getByText(/action performed/i)).toBeInTheDocument();
  });

  it('shows both requested and performed indicators', () => {
    renderHomePage();
    expect(screen.getByText(/action requested/i)).toBeInTheDocument();
    expect(screen.getByText(/action performed/i)).toBeInTheDocument();
  });

  it('has data-state="RECOVERY"', () => {
    renderHomePage();
    expect(document.querySelector('[data-state="RECOVERY"]')).toBeInTheDocument();
  });
});

describe('HomePage - Backend Error', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'error',
      credentials: null,
      session: null,
      decision: null,
      error: 'Device registration failed: HTTP 500',
      errorCode: 500,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows error state', () => {
    renderHomePage();
    expect(screen.getByText(/connection error/i)).toBeInTheDocument();
  });

  it('shows error message', () => {
    renderHomePage();
    expect(screen.getByText(/device registration failed/i)).toBeInTheDocument();
  });

  it('shows retry button', () => {
    renderHomePage();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('has role="alert"', () => {
    renderHomePage();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('HomePage - Backend Unavailable', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'unavailable',
      credentials: null,
      session: null,
      decision: null,
      error: 'Failed to fetch',
      errorCode: 0,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows unavailable state', () => {
    renderHomePage();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });

  it('shows reconnect button', () => {
    renderHomePage();
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
  });

  it('has role="alert"', () => {
    renderHomePage();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('HomePage - Active Session without Decision', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'pending-session-006',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 2,
        evidenceCount: 1,
      },
      decision: null,
      error: 'Decision unavailable: HTTP 404',
      errorCode: 404,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });
  });

  it('shows decision unavailable warning', () => {
    renderHomePage();
    // "Decision Unavailable" appears in the heading and the error message
    expect(screen.getAllByText(/decision unavailable/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows session context with pending status', () => {
    renderHomePage();
    expect(screen.getByText(/decision pending/i)).toBeInTheDocument();
  });

  it('still shows case ID', () => {
    renderHomePage();
    expect(screen.getByRole('text', { name: /session pending-session-006/i })).toBeInTheDocument();
  });
});

describe('HomePage - Accessibility', () => {
  it('no active session has accessible clear status', () => {
    mockUseHomeState.mockReturnValue({
      status: 'no_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: null,
      decision: null,
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });

    renderHomePage();
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('Clear'));
  });

  it('active session has accessible status badge', () => {
    mockUseHomeState.mockReturnValue({
      status: 'active_session',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'test',
        startedAt: '2026-09-03T10:00:00.000Z',
        eventCount: 1,
        evidenceCount: 1,
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: [],
        recommendedAction: 'Stay alert.',
        evidenceCount: 1,
        missingInformation: [],
        hasRequestedHighRiskAction: false,
        hasPerformedHighRiskAction: false,
        observations: [],
      },
      error: null,
      errorCode: null,
      refresh: vi.fn(),
      startSession: vi.fn(),
    });

    renderHomePage();
    const badges = screen.getAllByRole('status');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});
