/* ============================================================
   LUMINA Home Page (Front Door) Tests
   ============================================================
   Tests for all Home screen states.
   Mocking is used ONLY inside isolated tests.
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HomePage } from '@/app/HomePage';
import type { Incident, IncidentSummary } from '@/types/incident';

// ---- Mock the state hook ----
vi.mock('@/hooks/useHomeState', () => ({
  useHomeState: vi.fn(),
}));

import { useHomeState } from '@/hooks/useHomeState';
import { INCIDENT_STATUS_LABELS } from '@/hooks/useIncidentState';
const mockUseHomeState = vi.mocked(useHomeState);

const mockCredentials = { deviceId: 'test-device-1234abcd', deviceSecret: 'test-secret' };

function baseHomeState(overrides: Record<string, unknown> = {}) {
  return {
    status: 'ready',
    credentials: mockCredentials,
    incidents: [],
    incidentsStatus: 'ready' as const,
    incidentsError: null,
    activeIncident: null,
    error: null,
    errorCode: null,
    refresh: vi.fn(),
    ...overrides,
  };
}

function mockIncident(overrides: Record<string, unknown> = {}): Incident {
  return {
    incident_id: 'inc-test-0001',
    created_at: '2026-09-01T10:00:00.000Z',
    updated_at: '2026-09-01T10:30:00.000Z',
    status: 'ACTIVE',
    priority: 'HIGH',
    timeline: [],
    user_actions: [],
    exposure: {},
    unknowns: [],
    next_action: null,
    ...overrides,
  } as unknown as Incident;
}

function mockSummary(overrides: Partial<IncidentSummary> = {}): IncidentSummary {
  return {
    incident_id: 'inc-summary-0001',
    created_at: '2026-09-01T10:00:00.000Z',
    updated_at: '2026-09-01T10:30:00.000Z',
    status: 'MONITORING',
    priority: 'LOW',
    ...overrides,
  };
}

function renderHomePage() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<HomePage />} />
        <Route path="/incident/new" element={<span>PROBE-INCIDENT-NEW</span>} />
        <Route path="/incident" element={<span>PROBE-INCIDENT</span>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('HomePage - Loading State', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(baseHomeState({ status: 'loading' }) as never);
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

describe('HomePage - Front Door (ready, no active incident)', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(baseHomeState() as never);
  });

  it('shows "All Clear" status', () => {
    renderHomePage();
    const status = screen.getByRole('status', { name: /clear/i });
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('clear'));
  });

  it('shows the front door heading and call to action', () => {
    renderHomePage();
    expect(screen.getByRole('heading', { name: /something happened/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /start an incident/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('shows honest capability copy that never implies automatic recording', () => {
    renderHomePage();
    expect(screen.getByText(/never records your calls/i)).toBeInTheDocument();
  });

  it('starts a new incident from the hero call to action', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({ incidents: [mockSummary()], incidentsStatus: 'ready' }) as never,
    );
    renderHomePage();
    fireEvent.click(screen.getByRole('button', { name: /start an incident/i }));
    expect(screen.getByText(/PROBE-INCIDENT-NEW/)).toBeInTheDocument();
  });

  it('shows the empty recent-incidents state with a start action', () => {
    renderHomePage();
    expect(screen.getByText(/no incidents yet/i)).toBeInTheDocument();
  });

  it('does not leak engineering or backend detail', () => {
    renderHomePage();
    expect(screen.queryByText(/backend/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/endpoint/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/forensic/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/session listing/i)).not.toBeInTheDocument();
  });
});

describe('HomePage - Recent Incidents', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({ incidents: [mockSummary()], incidentsStatus: 'ready' }) as never,
    );
  });

  it('shows a real incident from the list', () => {
    renderHomePage();
    expect(screen.getByText(INCIDENT_STATUS_LABELS.MONITORING)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /inc-summary-0001/i })).toBeInTheDocument();
  });

  it('opens an incident from history', () => {
    renderHomePage();
    fireEvent.click(screen.getByRole('button', { name: /inc-summary-0001/i }));
    expect(screen.getByText(/PROBE-INCIDENT/)).toBeInTheDocument();
  });

  it('shows list credential failure honestly', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        incidentsStatus: 'unauthorized',
        incidentsError: 'Not authorized',
      }) as never,
    );
    renderHomePage();
    expect(screen.getByText(/incident history isn't available/i)).toBeInTheDocument();
  });

  it('shows a retry action when recent incidents fail to load', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        incidentsStatus: 'error',
        incidentsError: 'HTTP 500',
      }) as never,
    );
    renderHomePage();
    expect(screen.getByText(/couldn't load your recent incidents/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

describe('HomePage - Active Incident', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        activeIncident: mockIncident({ next_action: { action: 'Verify independently before sharing anything.', urgency: 'HIGH', reason: 'A code was requested.', official_channel_guidance: null } }),
      }) as never,
    );
  });

  it('shows the active incident card', () => {
    renderHomePage();
    expect(screen.getByText(/active incident/i)).toBeInTheDocument();
    expect(screen.getByText(/verify independently before sharing anything/i)).toBeInTheDocument();
  });

  it('does not show "All Clear" when an incident is active', () => {
    renderHomePage();
    expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
  });

  it('opens the incident view', () => {
    renderHomePage();
    fireEvent.click(screen.getByRole('button', { name: /open incident/i }));
    expect(screen.getByText(/PROBE-INCIDENT/)).toBeInTheDocument();
  });
});

describe('HomePage - Connection Error', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        status: 'error',
        error: 'Device registration failed: HTTP 500',
        errorCode: 500,
      }) as never,
    );
  });

  it('shows error state', () => {
    renderHomePage();
    expect(screen.getByText(/connection error/i)).toBeInTheDocument();
    expect(screen.getByText(/device registration failed/i)).toBeInTheDocument();
  });

  it('shows retry button and alert role', () => {
    renderHomePage();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('HomePage - Backend Unavailable', () => {
  beforeEach(() => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        status: 'unavailable',
        error: 'Failed to fetch',
        errorCode: 0,
      }) as never,
    );
  });

  it('shows unavailable state with reconnect', () => {
    renderHomePage();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('HomePage - Accessibility', () => {
  it('all-clear status is announced', () => {
    mockUseHomeState.mockReturnValue(baseHomeState() as never);
    renderHomePage();
    const status = screen.getByRole('status', { name: /clear/i });
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('clear'));
  });

  it('active incident status is announced', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        activeIncident: mockIncident(),
      }) as never,
    );
    renderHomePage();
    const status = screen.getByRole('status', { name: /active incident status/i });
    expect(status).toHaveAttribute('aria-label', expect.stringContaining('Active incident'));
  });
});

describe('HomePage - CP-30 recovery continuity', () => {
  it('shows a recovery record note on the active incident card', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        activeIncident: mockIncident({
          status: 'RECOVERING',
          next_action: {
            action: 'Change the password on the affected account.',
            urgency: 'HIGH',
            reason: 'A code was shared.',
            official_channel_guidance: null,
          },
          metadata: {
            recovery: {
              phase: 'AFTER_DAMAGE',
              short_description: 'Recovery record: a code was shared, reporting remains.',
            },
          },
        }),
      }) as never,
    );
    renderHomePage();
    expect(screen.getByRole('status', { name: /recovery record/i })).toBeInTheDocument();
    expect(screen.getByText(/Recovery record: a code was shared, reporting remains/)).toBeInTheDocument();
  });

  it('shows the recovery continuity note on a recent incident row', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        incidents: [
          mockSummary({
            status: 'RECOVERING',
            metadata: {
              recovery: {
                phase: 'AFTER_DAMAGE',
                short_description: 'In recovery: reporting remains.',
              },
            },
          }),
        ],
        incidentsStatus: 'ready',
      }) as never,
    );
    renderHomePage();
    expect(screen.getByText(/In recovery: reporting remains/)).toBeInTheDocument();
  });

  it('keeps pre-damage preventive incidents quiet in recent incidents', () => {
    mockUseHomeState.mockReturnValue(
      baseHomeState({
        incidents: [
          mockSummary({
            metadata: {
              recovery: { phase: 'BEFORE_DAMAGE', short_description: 'Preventive note' },
            },
          }),
        ],
        incidentsStatus: 'ready',
      }) as never,
    );
    renderHomePage();
    expect(screen.queryByText(/Preventive note/)).not.toBeInTheDocument();
  });
});
