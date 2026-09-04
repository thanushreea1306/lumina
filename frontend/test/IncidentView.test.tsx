/* ============================================================
   LUMINA Incident View Tests
   ============================================================
   Tests for the Incident Copilot frontend experience.
   ============================================================ */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { IncidentEntryPage } from '@/app/IncidentEntryPage';
import { IncidentViewPage } from '@/app/IncidentViewPage';
import { closeIncident, getIncident, addIncidentTranscript } from '@/lib/api/incidents';
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_PRIORITY_LABELS,
} from '@/hooks/useIncidentState';

// ---- Mock API calls ----
vi.mock('@/lib/api/device', () => ({
  ensureDeviceIdentity: vi.fn().mockResolvedValue({
    ok: true,
    data: { deviceId: 'test-device', deviceSecret: 'test-secret' },
  }),
}));

vi.mock('@/lib/api/incidents', () => ({
  createIncident: vi.fn().mockResolvedValue({
    ok: true,
    data: {
      incident_id: 'test-incident-123',
      created_at: '2024-01-01T00:00:00Z',
      status: 'ACTIVE',
      priority: 'NONE',
    },
  }),
  getIncident: vi.fn().mockResolvedValue({
    ok: true,
    data: {
      incident_id: 'test-incident-123',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      status: 'ACTION_REQUIRED',
      priority: 'HIGH',
      timeline: [
        {
          entry_id: 'entry-1',
          entry_type: 'INCIDENT_CREATED',
          sequence: 0,
          timestamp: '2024-01-01T00:00:00Z',
          summary: 'Incident created',
          epistemic_status: 'FACT',
          metadata: {},
        },
        {
          entry_id: 'entry-2',
          entry_type: 'EVIDENCE_ADDED',
          sequence: 1,
          timestamp: '2024-01-01T00:01:00Z',
          summary: 'Transcript evidence: OTP_REQUEST',
          epistemic_status: 'FACT',
          metadata: {
            observation_type: 'OTP_REQUEST',
            source: 'TRANSCRIPT',
            text_span: 'Give me your OTP',
            epistemic_note: 'Speaker requested OTP',
          },
        },
      ],
      user_actions: [],
      exposure: {
        AUTHENTICATION: {
          category: 'AUTHENTICATION',
          level: 'POTENTIALLY_EXPOSED',
          evidence_basis: 'OTP was requested',
          updated_at: '2024-01-01T00:01:00Z',
        },
      },
      unknowns: ['We do not know who is contacting you'],
      priority: 'HIGH',
      next_action: {
        action: 'Do not share the OTP. Pause and verify independently.',
        reason: 'Someone is requesting your OTP',
        evidence_basis: ['OTP/code requested'],
        urgency: 'IMMEDIATE',
        official_channel_guidance: 'Legitimate organizations never ask for OTPs by phone.',
      },
      session_ids: [],
      metadata: {},
    },
  }),
  addIncidentTranscript: vi.fn().mockResolvedValue({
    ok: true,
    data: {
      incident_id: 'test-incident-123',
      status: 'ACTION_REQUIRED',
      priority: 'HIGH',
      transcript_id: 'transcript-123',
      observations_extracted: 1,
      actions_extracted: 0,
      extraction: {
        transcript_id: 'transcript-123',
        observations: [
          {
            observation_type: 'OTP_REQUEST',
            confidence_in_extraction: 0.9,
            text_span: 'Give me your OTP',
            span_start: 0,
            span_end: 17,
            extraction_method: 'otp_request',
            epistemic_note: 'Speaker requested OTP',
          },
        ],
        user_actions: [],
        raw_text: 'Give me your OTP',
        extraction_timestamp: '2024-01-01T00:01:00Z',
      },
      next_action: {
        action: 'Do not share the OTP.',
        reason: 'OTP was requested',
        evidence_basis: ['OTP/code requested'],
        urgency: 'IMMEDIATE',
      },
      timeline_count: 2,
    },
  }),
  recordIncidentAction: vi.fn().mockResolvedValue({ ok: true, data: {} }),
  listIncidents: vi.fn().mockResolvedValue({ ok: true, data: { total: 0, incidents: [] } }),
  getIncidentNextAction: vi.fn().mockResolvedValue({ ok: true, data: { next_action: null } }),
  closeIncident: vi.fn().mockResolvedValue({
    ok: true,
    data: {
      incident_id: 'test-incident-123',
      status: 'CLOSED',
      closed: true,
      timeline_count: 3,
    },
  }),
}));

// ---- Helper ----
function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

// ---- Tests ----

describe('IncidentEntryPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('renders the incident entry page', () => {
    renderWithRouter(<IncidentEntryPage />);
    expect(screen.getByText('Incident Copilot')).toBeDefined();
    expect(screen.getByText('Start Incident')).toBeDefined();
  });

  it('shows supporting copy', () => {
    renderWithRouter(<IncidentEntryPage />);
    expect(screen.getByText(/Something suspicious happened/)).toBeDefined();
    expect(screen.getByText(/LUMINA can help you understand/)).toBeDefined();
  });

  it('has a start incident button', () => {
    renderWithRouter(<IncidentEntryPage />);
    const button = screen.getByRole('button', { name: /Start Incident/i });
    expect(button).toBeDefined();
  });
});

describe('IncidentViewPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
  });

  it('renders incident status', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Needs attention')).toBeDefined();
    });
  });

  it('renders next safest action', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText(/Do not share the OTP/)).toBeDefined();
    });
  });

  it('renders evidence section', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What LUMINA Identified')).toBeDefined();
    });
  });

  it('renders exposure panel', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What May Be at Risk')).toBeDefined();
      expect(screen.getByText('Authentication')).toBeDefined();
      expect(screen.getByText('Potentially exposed')).toBeDefined();
    });
  });

  it('renders unknown information', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText("What We Don't Know")).toBeDefined();
      expect(screen.getByText(/We do not know who is contacting you/)).toBeDefined();
    });
  });

  it('renders timeline', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Incident Timeline')).toBeDefined();
      expect(screen.getByText('Incident created')).toBeDefined();
    });
  });

  it('renders transcript input', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Add More Evidence')).toBeDefined();
      expect(screen.getByPlaceholderText(/Paste or type what was said/)).toBeDefined();
    });
  });

  it('renders user action confirmation', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Did You Already Act?')).toBeDefined();
      expect(screen.getByText('Yes, I did something')).toBeDefined();
      expect(screen.getByText('No, I did not')).toBeDefined();
    });
  });

  it('shows official channel guidance', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText(/Legitimate organizations never ask for OTPs by phone/)).toBeDefined();
    });
  });

  it('does not show numeric risk score', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.queryByText(/risk score/i)).toBeNull();
      expect(screen.queryByText(/scam probability/i)).toBeNull();
      expect(screen.queryByText(/confidence/i)).toBeNull();
    });
  });

  it('does not expose raw enum values in primary UI', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      // Should show human-readable labels, not raw enums
      expect(screen.queryByText('OTP_REQUEST')).toBeNull();
      expect(screen.queryByText('AUTHORITY_CLAIM')).toBeNull();
      expect(screen.queryByText('ACTION_REQUIRED')).toBeNull();
    });
  });
});

describe('Incident status labels', () => {
  it('has human-readable labels for all statuses', () => {
    expect(INCIDENT_STATUS_LABELS.ACTIVE).toBe('New incident');
    expect(INCIDENT_STATUS_LABELS.MONITORING).toBe('Being monitored');
    expect(INCIDENT_STATUS_LABELS.ACTION_REQUIRED).toBe('Needs attention');
    expect(INCIDENT_STATUS_LABELS.RECOVERING).toBe('Recovery in progress');
    expect(INCIDENT_STATUS_LABELS.CLOSED).toBe('Closed');
    expect(INCIDENT_STATUS_LABELS.UNKNOWN).toBe('Status unknown');
  });

  it('has human-readable labels for all priorities', () => {
    expect(INCIDENT_PRIORITY_LABELS.IMMEDIATE).toBe('Immediate');
    expect(INCIDENT_PRIORITY_LABELS.HIGH).toBe('High');
    expect(INCIDENT_PRIORITY_LABELS.MEDIUM).toBe('Medium');
    expect(INCIDENT_PRIORITY_LABELS.LOW).toBe('Low');
    expect(INCIDENT_PRIORITY_LABELS.NONE).toBe('No priority');
  });
});

describe('IncidentViewPage - empty state', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('shows no active incident when no incident ID stored', () => {
    renderWithRouter(<IncidentViewPage />);
    expect(screen.getByText('No active incident')).toBeDefined();
  });
});

describe('IncidentViewPage - End (Close)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
    vi.mocked(closeIncident).mockReset();
  });

  it('calls the real close endpoint and clears local state on success', async () => {
    vi.mocked(closeIncident).mockResolvedValue({
      ok: true,
      data: {
        incident_id: 'test-incident-123',
        status: 'CLOSED',
        closed: true,
        timeline_count: 3,
      },
    });

    renderWithRouter(<IncidentViewPage />);
    const endButton = await screen.findByRole('button', { name: 'End' });
    fireEvent.click(endButton);

    await waitFor(() => {
      expect(closeIncident).toHaveBeenCalledTimes(1);
    });
    // After server success, the stored incident id is cleared.
    await waitFor(() => {
      expect(sessionStorage.getItem('lumina_current_incident_id')).toBeNull();
    });
  });

  it('keeps the incident id and shows an error when closing fails', async () => {
    vi.mocked(closeIncident).mockResolvedValue({
      ok: false,
      status: 500,
      error: 'server exploded',
    });

    renderWithRouter(<IncidentViewPage />);
    const endButton = await screen.findByRole('button', { name: 'End' });
    fireEvent.click(endButton);

    await waitFor(() => {
      expect(screen.getByText(/Could not close incident/)).toBeDefined();
    });
    // The incident id is preserved so the user can retry.
    expect(sessionStorage.getItem('lumina_current_incident_id')).toBe(
      'test-incident-123',
    );
    // The incident view is still shown (not cleared to idle).
    expect(screen.getByText('Needs attention')).toBeDefined();
  });

  it('does not clear local state before the server confirms closure', async () => {
    // A pending (never-resolving) close should not clear the incident id.
    vi.mocked(closeIncident).mockReturnValue(new Promise(() => {}));

    renderWithRouter(<IncidentViewPage />);
    const endButton = await screen.findByRole('button', { name: 'End' });
    fireEvent.click(endButton);

    await waitFor(() => {
      expect(closeIncident).toHaveBeenCalled();
    });
    // Local state still present while the close is pending.
    expect(sessionStorage.getItem('lumina_current_incident_id')).toBe(
      'test-incident-123',
    );
  });
});

describe('IncidentViewPage - transcript idempotency', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
    addIncidentTranscript.mockClear();
    // Default mock: always succeed (used by repeated submissions).
    addIncidentTranscript.mockResolvedValue({
      ok: true,
      data: {
        incident_id: 'test-incident-123',
        status: 'ACTION_REQUIRED',
        priority: 'HIGH',
        transcript_id: 'transcript-123',
        observations_extracted: 1,
        actions_extracted: 0,
        extraction: {
          transcript_id: 'transcript-123',
          observations: [],
          user_actions: [],
          raw_text: '',
          extraction_timestamp: '2024-01-01T00:01:00Z',
        },
        next_action: null,
        timeline_count: 2,
      },
    });
  });

  it('reuses the same batch_id when the same text is submitted again', async () => {
    renderWithRouter(<IncidentViewPage />);

    const textarea = await screen.findByPlaceholderText(/Paste or type what was said/);
    const submitButton = screen.getByRole('button', { name: 'Submit Transcript' });

    // First submission
    fireEvent.change(textarea, { target: { value: 'Give me your OTP' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(addIncidentTranscript).toHaveBeenCalledTimes(1);
    });
    const firstId = addIncidentTranscript.mock.calls[0][2].batch_id;
    expect(firstId).toBeTruthy();

    // Second submission of the SAME text (e.g. a network retry / double-tap)
    fireEvent.change(textarea, { target: { value: 'Give me your OTP' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(addIncidentTranscript).toHaveBeenCalledTimes(2);
    });
    const secondId = addIncidentTranscript.mock.calls[1][2].batch_id;

    // The SAME stable id is reused → backend can deduplicate.
    expect(secondId).toBe(firstId);
  });

  it('uses a different batch_id for different text', async () => {
    renderWithRouter(<IncidentViewPage />);

    const textarea = await screen.findByPlaceholderText(/Paste or type what was said/);
    const submitButton = screen.getByRole('button', { name: 'Submit Transcript' });

    fireEvent.change(textarea, { target: { value: 'Give me your OTP' } });
    fireEvent.click(submitButton);
    await waitFor(() => expect(addIncidentTranscript).toHaveBeenCalledTimes(1));
    const firstId = addIncidentTranscript.mock.calls[0][2].batch_id;

    fireEvent.change(textarea, { target: { value: 'Give me your password' } });
    fireEvent.click(submitButton);
    await waitFor(() => expect(addIncidentTranscript).toHaveBeenCalledTimes(2));
    const secondId = addIncidentTranscript.mock.calls[1][2].batch_id;

    expect(secondId).not.toBe(firstId);
  });

  it('does not use a timestamp as the idempotency key', async () => {
    renderWithRouter(<IncidentViewPage />);

    const textarea = await screen.findByPlaceholderText(/Paste or type what was said/);
    const submitButton = screen.getByRole('button', { name: 'Submit Transcript' });

    fireEvent.change(textarea, { target: { value: 'Give me your OTP' } });
    fireEvent.click(submitButton);
    await waitFor(() => expect(addIncidentTranscript).toHaveBeenCalledTimes(1));
    const firstId = addIncidentTranscript.mock.calls[0][2].batch_id;

    // Same text submitted again → identical id (proves the key is content, not time).
    fireEvent.change(textarea, { target: { value: 'Give me your OTP' } });
    fireEvent.click(submitButton);
    await waitFor(() => expect(addIncidentTranscript).toHaveBeenCalledTimes(2));
    const secondId = addIncidentTranscript.mock.calls[1][2].batch_id;

    expect(secondId).toBe(firstId);
  });
});

describe('IncidentViewPage - CLOSED incident', () => {
  function closedIncident() {
    return {
      incident_id: 'test-incident-closed',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:05:00Z',
      status: 'CLOSED',
      priority: 'NONE',
      timeline: [
        {
          entry_id: 'entry-1',
          entry_type: 'INCIDENT_CREATED',
          sequence: 0,
          timestamp: '2024-01-01T00:00:00Z',
          summary: 'Incident created',
          epistemic_status: 'FACT',
          metadata: {},
        },
        {
          entry_id: 'entry-2',
          entry_type: 'INCIDENT_CLOSED',
          sequence: 1,
          timestamp: '2024-01-01T00:05:00Z',
          summary: 'Incident closed',
          epistemic_status: 'FACT',
          metadata: { source: 'OWNER' },
        },
      ],
      user_actions: [],
      exposure: {},
      unknowns: [],
      next_action: null,
      session_ids: [],
      metadata: {},
    };
  }

  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-closed');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: closedIncident() } as never);
    vi.mocked(closeIncident).mockReset();
    vi.mocked(closeIncident).mockResolvedValue({
      ok: true,
      data: {
        incident_id: 'test-incident-closed',
        status: 'CLOSED',
        closed: true,
        timeline_count: 3,
      },
    });
  });

  it('hides the End button for a CLOSED incident', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Closed')).toBeDefined();
    });
    expect(screen.queryByRole('button', { name: 'End' })).toBeNull();
  });

  it('shows the closed archival banner', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText(/closed and archived/i)).toBeDefined();
    });
  });

  it('disables transcript submission for a CLOSED incident', async () => {
    renderWithRouter(<IncidentViewPage />);
    const textarea = await screen.findByPlaceholderText(/Paste or type what was said/);
    fireEvent.change(textarea, { target: { value: 'some evidence text' } });

    const submitButton = screen.getByRole('button', { name: 'Submit Transcript' }) as HTMLButtonElement;
    expect(submitButton.disabled).toBe(true);
  });
});
