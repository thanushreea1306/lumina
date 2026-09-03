/* ============================================================
   LUMINA Evidence Board Tests
   ============================================================
   Tests for all Evidence Board states:
   - No session
   - No evidence
   - Evidence with all statuses
   - Evidence with all sources
   - Evidence detail panel
   - Timeline
   - Backend error / unavailable
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { EvidencePage } from '@/app/EvidencePage';

vi.mock('@/hooks/useSessionState', () => ({
  useSessionState: vi.fn(),
}));

vi.mock('@/hooks/useHomeState', () => ({
  useHomeState: vi.fn(),
}));

import { useSessionState } from '@/hooks/useSessionState';
const mockUseSessionState = vi.mocked(useSessionState);

function renderEvidencePage() {
  return render(
    <BrowserRouter>
      <EvidencePage />
    </BrowserRouter>,
  );
}

describe('EvidencePage - No Session', () => {
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

  it('shows evidence board heading', () => {
    renderEvidencePage();
    expect(screen.getByText(/evidence board/i)).toBeInTheDocument();
  });

  it('shows no active session state', () => {
    renderEvidencePage();
    expect(screen.getByText(/no active session/i)).toBeInTheDocument();
  });

  it('explains what evidence is', () => {
    renderEvidencePage();
    expect(screen.getByText(/each piece of evidence/i)).toBeInTheDocument();
  });
});

describe('EvidencePage - Loading', () => {
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
    renderEvidencePage();
    expect(screen.getAllByText(/loading evidence/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('EvidencePage - Unavailable', () => {
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
    renderEvidencePage();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
  });
});

describe('EvidencePage - No Evidence', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'empty-session-001',
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

  it('shows no evidence recorded', () => {
    renderEvidencePage();
    // Both the heading "No Evidence Recorded" and the subtitle "No evidence recorded yet" match
    expect(screen.getAllByText(/no evidence recorded/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows zero evidence count', () => {
    renderEvidencePage();
    // The subtitle shows the count text "No evidence recorded yet"
    expect(screen.getByText(/no evidence recorded yet/i)).toBeInTheDocument();
  });
});

describe('EvidencePage - Evidence with USER_CONFIRMED status', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'ev-session-002',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [
          {
            evidence_id: 'ev-001',
            type: 'AUTHORITY_CLAIM',
            value: true,
            status: 'USER_CONFIRMED',
            source: 'USER',
            timestamp: '2026-09-03T10:01:00.000Z',
            sequence: 0,
            confidence: null,
            metadata: {},
          },
        ],
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: ['caller claimed to be from an authority'],
        recommendedAction: 'Stay alert.',
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

  it('shows evidence count', () => {
    renderEvidencePage();
    expect(screen.getByText(/1 piece of evidence/i)).toBeInTheDocument();
  });

  it('shows evidence type label', () => {
    renderEvidencePage();
    // Type appears in card and timeline — use getAllByText
    expect(screen.getAllByText(/authority claim/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows User Confirmed status', () => {
    renderEvidencePage();
    expect(screen.getAllByText(/user confirmed/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows User source group', () => {
    renderEvidencePage();
    expect(screen.getByText(/user — 1 item/i)).toBeInTheDocument();
  });

  it('shows evidence timeline', () => {
    renderEvidencePage();
    expect(screen.getByText(/evidence timeline/i)).toBeInTheDocument();
  });
});

describe('EvidencePage - Evidence with OBSERVED status', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'ev-session-003',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [
          {
            evidence_id: 'ev-002',
            type: 'call_lifecycle',
            value: { direction: 'incoming', duration_ms: 120000 },
            status: 'OBSERVED',
            source: 'DEVICE',
            timestamp: '2026-09-03T10:00:30.000Z',
            sequence: 0,
            confidence: null,
            metadata: {},
          },
        ],
      },
      decision: {
        state: 'CLEAR',
        stateLabel: 'Clear',
        reasonCodes: [],
        recommendedAction: 'No action needed.',
        evidenceCount: 1,
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

  it('shows Observed status', () => {
    renderEvidencePage();
    expect(screen.getAllByText(/observed/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows Device source', () => {
    renderEvidencePage();
    expect(screen.getByText(/device — 1 item/i)).toBeInTheDocument();
  });

  it('shows call lifecycle type', () => {
    renderEvidencePage();
    // Type appears in card and in timeline — use getAllByText
    expect(screen.getAllByText(/call lifecycle/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('EvidencePage - Multiple evidence sources', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'ev-session-004',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [
          {
            evidence_id: 'ev-003',
            type: 'AUTHORITY_CLAIM',
            value: true,
            status: 'USER_CONFIRMED',
            source: 'USER',
            timestamp: '2026-09-03T10:01:00.000Z',
            sequence: 0,
            confidence: null,
            metadata: {},
          },
          {
            evidence_id: 'ev-004',
            type: 'call_lifecycle',
            value: { direction: 'incoming' },
            status: 'OBSERVED',
            source: 'DEVICE',
            timestamp: '2026-09-03T10:00:30.000Z',
            sequence: 1,
            confidence: null,
            metadata: {},
          },
        ],
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: [],
        recommendedAction: 'Stay alert.',
        evidenceCount: 2,
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

  it('shows 2 pieces of evidence', () => {
    renderEvidencePage();
    expect(screen.getByText(/2 pieces/i)).toBeInTheDocument();
  });

  it('shows both source groups', () => {
    renderEvidencePage();
    // USER and DEVICE source groups
    const userGroup = screen.getByText(/user — 1 item/i);
    const deviceGroup = screen.getByText(/device — 1 item/i);
    expect(userGroup).toBeInTheDocument();
    expect(deviceGroup).toBeInTheDocument();
  });
});

describe('EvidencePage - Evidence detail panel', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'ev-session-005',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [
          {
            evidence_id: 'ev-detail-001',
            type: 'OTP_REQUEST',
            value: true,
            status: 'USER_CONFIRMED',
            source: 'USER',
            timestamp: '2026-09-03T10:05:00.000Z',
            sequence: 0,
            confidence: null,
            metadata: { notes: 'Caller asked for OTP' },
          },
        ],
      },
      decision: {
        state: 'PAUSE',
        stateLabel: 'Pause',
        reasonCodes: ['asked for an OTP/code'],
        recommendedAction: 'Do not share OTPs.',
        evidenceCount: 1,
        missingInformation: [],
        observations: ['OTP_REQUEST'],
        hasRequestedHighRiskAction: true,
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

  it('opens detail panel when evidence card is clicked', () => {
    renderEvidencePage();
    const card = screen.getByRole('button', { name: /evidence: otp request/i });
    fireEvent.click(card);
    expect(screen.getByRole('dialog', { name: /evidence detail/i })).toBeInTheDocument();
  });

  it('detail panel shows evidence type', () => {
    renderEvidencePage();
    fireEvent.click(screen.getByRole('button', { name: /evidence: otp request/i }));
    // Type appears in card label, detail panel header, and detail panel body
    expect(screen.getAllByText(/otp request/i).length).toBeGreaterThanOrEqual(2);
  });

  it('detail panel shows evidence ID', () => {
    renderEvidencePage();
    fireEvent.click(screen.getByRole('button', { name: /evidence: otp request/i }));
    expect(screen.getByText('ev-detail-001')).toBeInTheDocument();
  });

  it('detail panel shows metadata', () => {
    renderEvidencePage();
    fireEvent.click(screen.getByRole('button', { name: /evidence: otp request/i }));
    expect(screen.getByText(/caller asked for otp/i)).toBeInTheDocument();
  });

  it('detail panel has close button', () => {
    renderEvidencePage();
    fireEvent.click(screen.getByRole('button', { name: /evidence: otp request/i }));
    // The backdrop has aria-label "Close detail panel" and the button has "Close"
    // Use exact match for the close button
    expect(screen.getAllByRole('button', { name: /close/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('detail panel closes when close button is clicked', () => {
    renderEvidencePage();
    fireEvent.click(screen.getByRole('button', { name: /evidence: otp request/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    // Click the actual close button (not the backdrop) by finding the one inside the dialog
    const dialog = screen.getByRole('dialog');
    const closeButton = dialog.querySelector('button[aria-label="Close"]');
    expect(closeButton).toBeTruthy();
    fireEvent.click(closeButton!);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('EvidencePage - Accessibility', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'active',
      credentials: { deviceId: 'test', deviceSecret: 'test' },
      session: {
        sessionId: 'ev-session-006',
        startedAt: '2026-09-03T10:00:00.000Z',
        events: [],
        evidence: [
          {
            evidence_id: 'ev-a11y-001',
            type: 'MONEY_REQUEST',
            value: true,
            status: 'USER_CONFIRMED',
            source: 'USER',
            timestamp: '2026-09-03T10:03:00.000Z',
            sequence: 0,
            confidence: null,
            metadata: {},
          },
        ],
      },
      decision: {
        state: 'WATCH',
        stateLabel: 'Watch',
        reasonCodes: [],
        recommendedAction: 'Stay alert.',
        evidenceCount: 1,
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

  it('evidence cards are clickable buttons', () => {
    renderEvidencePage();
    const cards = screen.getAllByRole('button').filter(
      (b) => b.getAttribute('aria-label')?.includes('Evidence:')
    );
    expect(cards.length).toBeGreaterThan(0);
  });

  it('evidence cards have descriptive aria-labels', () => {
    renderEvidencePage();
    const card = screen.getByRole('button', { name: /evidence: money request/i });
    // aria-label is "Evidence: Money Request" — check it contains the evidence type
    expect(card).toHaveAttribute('aria-label', expect.stringContaining('Money Request'));
  });

  it('timeline has role="list"', () => {
    renderEvidencePage();
    const timeline = screen.getByRole('list', { name: /evidence timeline/i });
    expect(timeline).toBeInTheDocument();
  });

  it('evidence status is not conveyed by color alone', () => {
    renderEvidencePage();
    // Status badges should have text labels
    expect(screen.getAllByText(/user confirmed/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('EvidencePage - Backend Error', () => {
  beforeEach(() => {
    mockUseSessionState.mockReturnValue({
      status: 'error',
      credentials: null,
      session: null,
      decision: null,
      error: 'HTTP 500',
      errorCode: 500,
      startNewSession: vi.fn(),
      submitObservation: vi.fn(),
      submitEvent: vi.fn(),
      refresh: vi.fn(),
      endSession: vi.fn(),
    });
  });

  it('shows error state', () => {
    renderEvidencePage();
    expect(screen.getByText(/evidence unavailable/i)).toBeInTheDocument();
  });

  it('shows retry button', () => {
    renderEvidencePage();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});
