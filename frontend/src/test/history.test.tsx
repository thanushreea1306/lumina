/* ============================================================
   LUMINA Incident History Page Tests
   ============================================================
   Tests for all History screen states.
   Mocking is used ONLY inside isolated tests.
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HistoryPage } from '@/app/HistoryPage';
import type { IncidentSummary } from '@/types/incident';

// ---- Mock the state hook ----
vi.mock('@/hooks/useIncidentList', () => ({
  useIncidentList: vi.fn(),
}));

import { useIncidentList } from '@/hooks/useIncidentList';
import { INCIDENT_STATUS_LABELS } from '@/hooks/useIncidentState';
const mockUseIncidentList = vi.mocked(useIncidentList);

function mockSummary(overrides: Partial<IncidentSummary> = {}): IncidentSummary {
  return {
    incident_id: 'inc-history-0001',
    created_at: '2026-09-01T10:00:00.000Z',
    updated_at: '2026-09-01T10:30:00.000Z',
    status: 'CLOSED',
    priority: 'MEDIUM',
    ...overrides,
  };
}

function baseListState(overrides: Record<string, unknown> = {}) {
  return {
    status: 'loading' as const,
    credentials: null,
    incidents: [],
    error: null,
    errorCode: null,
    refresh: vi.fn(),
    ...overrides,
  };
}

function renderHistory() {
  return render(
    <MemoryRouter initialEntries={['/history']}>
      <Routes>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/incident" element={<span>PROBE-INCIDENT</span>} />
        <Route path="/incident/new" element={<span>PROBE-INCIDENT-NEW</span>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('HistoryPage - Loading', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(baseListState() as never);
  });

  it('shows a loading state', () => {
    renderHistory();
    expect(screen.getAllByText(/loading your history/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('HistoryPage - Empty', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(
      baseListState({ status: 'ready', incidents: [] }) as never,
    );
  });

  it('shows an honest empty state', () => {
    renderHistory();
    expect(screen.getByRole('heading', { name: /incident history/i })).toBeInTheDocument();
    expect(screen.getByText(/no incidents yet/i)).toBeInTheDocument();
  });

  it('starts a new incident from the empty state', () => {
    renderHistory();
    fireEvent.click(screen.getByRole('button', { name: /start an incident/i }));
    expect(screen.getByText(/PROBE-INCIDENT-NEW/)).toBeInTheDocument();
  });

  it('does not leak engineering or backend detail', () => {
    renderHistory();
    expect(screen.queryByText(/session listing/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/endpoint/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/backend/i)).not.toBeInTheDocument();
  });
});

describe('HistoryPage - Populated', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(
      baseListState({
        status: 'ready',
        incidents: [mockSummary()],
      }) as never,
    );
  });

  it('shows real incidents', () => {
    renderHistory();
    expect(screen.getByText(INCIDENT_STATUS_LABELS.CLOSED)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /inc-history-0001/i })).toBeInTheDocument();
  });

  it('opens an incident from the list', () => {
    renderHistory();
    fireEvent.click(screen.getByRole('button', { name: /inc-history-0001/i }));
    expect(screen.getByText(/PROBE-INCIDENT/)).toBeInTheDocument();
  });

  it('offers a new incident action', () => {
    renderHistory();
    expect(screen.getByRole('button', { name: /start a new incident/i })).toBeInTheDocument();
  });
});

describe('HistoryPage - Credential / Ownership', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(
      baseListState({ status: 'unauthorized', error: 'Not authorized' }) as never,
    );
  });

  it('explains history is device-bound honestly', () => {
    renderHistory();
    expect(screen.getByText(/incident history isn't available/i)).toBeInTheDocument();
    expect(screen.getByText(/device that created it/i)).toBeInTheDocument();
  });
});

describe('HistoryPage - Error', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(
      baseListState({ status: 'error', error: 'HTTP 500', errorCode: 500 }) as never,
    );
  });

  it('shows a retryable error state', () => {
    renderHistory();
    expect(screen.getByText(/could not load your history/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});

describe('HistoryPage - Unavailable', () => {
  beforeEach(() => {
    mockUseIncidentList.mockReturnValue(
      baseListState({ status: 'unavailable', error: 'Failed to fetch', errorCode: 0 }) as never,
    );
  });

  it('shows an unavailable state with reconnect', () => {
    renderHistory();
    expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
  });
});

describe('HistoryPage - CP-30 recovery continuity', () => {
  it('shows the recovery note instead of a raw id slice', () => {
    mockUseIncidentList.mockReturnValue(
      baseListState({
        status: 'ready',
        incidents: [
          mockSummary({
            status: 'RECOVERING',
            metadata: {
              recovery: {
                phase: 'AFTER_DAMAGE',
                short_description: 'In recovery: code shared, reporting remains.',
              },
            },
          }),
        ],
      }) as never,
    );
    renderHistory();
    expect(screen.getByText(/In recovery: code shared, reporting remains/)).toBeInTheDocument();
    // The raw id prefix is not shown to the user.
    expect(screen.queryByText(/inc-history-0001/i)).toBeNull();
  });

  it('keeps closed records continuity honest without raw ids', () => {
    mockUseIncidentList.mockReturnValue(
      baseListState({
        status: 'ready',
        incidents: [
          mockSummary({
            status: 'CLOSED',
            metadata: {
              recovery: {
                phase: 'AFTER_DAMAGE',
                short_description: 'Closed record: recovery steps documented.',
              },
            },
          }),
        ],
      }) as never,
    );
    renderHistory();
    expect(screen.getByText(/Closed record: recovery steps documented/)).toBeInTheDocument();
    expect(screen.queryByText(/inc-history-0001/i)).toBeNull();
  });
});