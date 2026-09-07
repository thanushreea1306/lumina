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
import { getTrustedContact } from '@/lib/api/account';
import { requestHelp } from '@/lib/api/help';
import type { InterventionDecision } from '@/types/incident';

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

vi.mock('@/lib/api/account', () => ({
  getTrustedContact: vi.fn().mockResolvedValue({
    configured: false,
    contact: null,
  }),
}));

vi.mock('@/lib/api/help', () => ({
  requestHelp: vi.fn().mockResolvedValue({
    incident_id: 'test-incident-123',
    help_story: {
      incident_id: 'test-incident-123',
      generated_at: '2024-01-01T00:01:00Z',
      urgency: 'HIGH',
      one_line_summary: 'A verification code was requested during a call.',
      sections: [],
      privacy_note: 'This summary is shown only to your trusted contact.',
    },
    help_story_text: '',
    already_requested: false,
    trusted_contact_notified: false,
    delivery_status: 'DELIVERED',
    trusted_contact_configured: true,
    delivery_channel: 'SMS',
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
      // The unknown is surfaced honestly both in the current situation and in
      // the dedicated open-questions section below it.
      expect(screen.getAllByText(/We do not know who is contacting you/).length).toBeGreaterThan(0);
    });
  });

  it('renders timeline', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Conversation$/i })).toBeDefined();
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

describe('IncidentViewPage - CP-28B live incident centerpiece', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
  });

  it('renders the LIVE INCIDENT masthead with a status heading', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Live incident')).toBeDefined();
      // The status word doubles as a polite live-region announcement.
      expect(screen.getByRole('status', { name: /Incident status: Needs attention/i })).toBeDefined();
    });
  });

  it('shows the current situation in plain language derived from evidence', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Current Situation')).toBeDefined();
      expect(screen.getAllByText(/LUMINA recorded: A verification code was requested/i).length).toBeGreaterThan(0);
    });
  });

  it('shows a dominant Next Safe Action from the backend', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /next safe action/i })).toBeDefined();
      expect(screen.getByText(/Do not share the OTP/)).toBeDefined();
    });
  });

  it('keeps I\'M TRAPPED — GET HELP prominent and independent of audio/ML', async () => {
    renderWithRouter(<IncidentViewPage />);
    const trappedButton = await screen.findByRole('button', { name: /I'M TRAPPED/i });
    expect(trappedButton).toBeDefined();
    // Emphasises independence from the microphone, speech recognition, and analysis.
    expect(screen.getByText(/separately from the microphone/i)).toBeDefined();
  });

  it('moves the engineering analysis behind a Technical Analysis disclosure', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What May Be at Risk')).toBeDefined();
    });
    const details = screen.getByText('Technical Analysis').closest('details');
    expect(details).not.toBeNull();
  });

  it('keeps audio copy honest about call recording', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Analyze Conversation/i })).toBeDefined();
      expect(screen.getByText(/LUMINA never records your calls without asking/i)).toBeDefined();
    });
  });

  it('never converts an UNKNOWN exposure into something safe', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What May Be at Risk')).toBeDefined();
    });
    // Only backend-confirmed exposure appears — nothing is invented here.
    expect(screen.getByText('Potentially exposed')).toBeDefined();
    expect(screen.getByText('Authentication')).toBeDefined();
  });
});

describe('IncidentViewPage - exposure honesty (CP-28B)', () => {
  function unknownExposureIncident() {
    return {
      incident_id: 'test-incident-unknown-exp',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      status: 'ACTION_REQUIRED',
      priority: 'HIGH',
      timeline: [],
      user_actions: [],
      exposure: {
        AUTHENTICATION: {
          category: 'AUTHENTICATION',
          level: 'UNKNOWN',
          evidence_basis: 'No evidence yet',
          updated_at: '2024-01-01T00:00:00Z',
        },
      },
      unknowns: [],
      next_action: null,
      session_ids: [],
      metadata: {},
    };
  }

  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-unknown-exp');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: unknownExposureIncident() } as never);
  });

  it('shows an UNKNOWN exposure level as unknown, never as safe', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Authentication')).toBeDefined();
      expect(screen.getByText('Unknown')).toBeDefined();
    });
    expect(screen.queryByText('Not indicated')).toBeNull();
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

// ---- CP-28C fixtures ----

// Mirrors the default getIncident mock so suites can restore a fresh
// realistic incident after other suites have reset the shared mock.
function defaultIncident() {
  return {
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
    next_action: {
      action: 'Do not share the OTP. Pause and verify independently.',
      reason: 'Someone is requesting your OTP',
      evidence_basis: ['OTP/code requested'],
      urgency: 'IMMEDIATE',
      official_channel_guidance: 'Legitimate organizations never ask for OTPs by phone.',
    },
    session_ids: [],
    metadata: {},
  };
}

function calmIncident() {
  return {
    incident_id: 'test-incident-calm',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    status: 'ACTIVE',
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
    ],
    user_actions: [],
    exposure: {},
    unknowns: [],
    next_action: null,
    session_ids: [],
    metadata: {},
  };
}

function pressureIncident() {
  return {
    incident_id: 'test-incident-pressure',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    status: 'ACTIVE',
    priority: 'HIGH',
    timeline: [
      {
        entry_id: 'entry-0',
        entry_type: 'INCIDENT_CREATED',
        sequence: 0,
        timestamp: '2024-01-01T00:00:00Z',
        summary: 'Incident created',
        epistemic_status: 'FACT',
        metadata: {},
      },
      {
        entry_id: 'entry-1',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 1,
        timestamp: '2024-01-01T00:01:00Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          observation_type: 'AUTHORITY_CLAIM',
          source: 'TRANSCRIPT',
          text_span: 'I am from the police',
          epistemic_note: '',
        },
      },
      {
        entry_id: 'entry-2',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 2,
        timestamp: '2024-01-01T00:01:10Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          observation_type: 'URGENCY',
          source: 'TRANSCRIPT',
          text_span: 'You have to act now',
          epistemic_note: '',
        },
      },
      {
        entry_id: 'entry-3',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 3,
        timestamp: '2024-01-01T00:01:20Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          observation_type: 'OTP_REQUEST',
          source: 'TRANSCRIPT',
          text_span: 'Give me the code',
          epistemic_note: '',
        },
      },
    ],
    user_actions: [],
    exposure: {},
    unknowns: [],
    next_action: null,
    session_ids: [],
    metadata: {
      escalation: {
        has_escalation: true,
        patterns: [],
        repeated_requests: [],
        verified_using: [],
      },
    },
  };
}

function conversationIncident() {
  return {
    incident_id: 'test-incident-conv',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    status: 'ACTION_REQUIRED',
    priority: 'HIGH',
    timeline: [
      {
        entry_id: 'c1',
        entry_type: 'INCIDENT_CREATED',
        sequence: 0,
        timestamp: '2024-01-01T00:00:00Z',
        summary: 'Incident created',
        epistemic_status: 'FACT',
        metadata: {},
      },
      {
        entry_id: 'c2',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 1,
        timestamp: '2024-01-01T00:01:00Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          source: 'TRANSCRIPT',
          observation_type: 'OTP_REQUEST',
          text_span: 'Give me your OTP',
          speaker: 'CALLER',
          epistemic_note: '',
        },
      },
      {
        entry_id: 'c3',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 2,
        timestamp: '2024-01-01T00:01:10Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          source: 'TRANSCRIPT',
          observation_type: 'URGENCY',
          text_span: 'I need it right now',
          speaker: 'USER',
          epistemic_note: '',
        },
      },
      {
        entry_id: 'c4',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 3,
        timestamp: '2024-01-01T00:01:20Z',
        summary: '',
        epistemic_status: 'FACT',
        metadata: {
          source: 'TRANSCRIPT',
          observation_type: 'URGENCY',
          text_span: 'Just do it',
          speaker: 'UNKNOWN',
          epistemic_note: '',
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
    unknowns: [],
    next_action: {
      action: 'Do not share the OTP.',
      reason: 'OTP was requested',
      evidence_basis: ['OTP/code requested'],
      urgency: 'IMMEDIATE',
      official_channel_guidance: 'Legitimate organizations never ask for OTPs by phone.',
    },
    session_ids: [],
    metadata: {},
  };
}

function claimedIncident() {
  return {
    incident_id: 'test-incident-claim',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    status: 'ACTION_REQUIRED',
    priority: 'HIGH',
    timeline: [
      {
        entry_id: 'tc-1',
        entry_type: 'INCIDENT_CREATED',
        sequence: 0,
        timestamp: '2024-01-01T00:00:00Z',
        summary: 'Incident created',
        epistemic_status: 'FACT',
        metadata: {},
      },
      {
        entry_id: 'tc-2',
        entry_type: 'EVIDENCE_ADDED',
        sequence: 1,
        timestamp: '2024-01-01T00:01:00Z',
        summary: '',
        epistemic_status: 'INFERENCE',
        metadata: {
          source: 'TRANSCRIPT_CLAIM',
          claimed_action_type: 'SHARED_OTP',
          claimed_description: 'the caller said the victim shared the code',
        },
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

function confirmedIncident() {
  return {
    incident_id: 'test-incident-confirmed',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    status: 'ACTION_REQUIRED',
    priority: 'HIGH',
    timeline: [
      {
        entry_id: 'cf-1',
        entry_type: 'INCIDENT_CREATED',
        sequence: 0,
        timestamp: '2024-01-01T00:00:00Z',
        summary: 'Incident created',
        epistemic_status: 'FACT',
        metadata: {},
      },
      {
        entry_id: 'cf-2',
        entry_type: 'USER_ACTION_RECORDED',
        sequence: 1,
        timestamp: '2024-01-01T00:02:00Z',
        summary: 'User confirmed: shared code',
        epistemic_status: 'FACT',
        metadata: {
          action_type: 'SHARED_OTP',
          source: 'USER_CONFIRMATION',
        },
      },
    ],
    user_actions: [
      {
        action_id: 'ua-1',
        action_type: 'SHARED_OTP',
        description: 'shared code',
        timestamp: '2024-01-01T00:02:00Z',
        sequence: 0,
      },
    ],
    exposure: {},
    unknowns: [],
    next_action: null,
    session_ids: [],
    metadata: {},
  };
}

// ---- CP-28C: hero states & calm intervention ----

describe('IncidentViewPage - CP-28C hero states', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-calm');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: calmIncident() } as never);
  });

  it('shows a calm hero when only an open incident exists', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('status', { name: /Incident status: New incident/i })).toBeDefined();
    });
    expect(screen.getByText('LUMINA is watching this conversation. Nothing concerning has been recorded yet.')).toBeDefined();
  });

  it('offers a calm intervention as the next safe action only when supported', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /next safe action/i })).toBeDefined();
    });
    expect(screen.getByText(/Pause. You don't have to decide right now/i)).toBeDefined();
  });

  it('does not show a pressure story when nothing concerning was recorded', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Live incident')).toBeDefined();
    });
    expect(screen.queryByText('How the Pressure Built')).toBeNull();
    expect(screen.queryByText(/increasing pressure/i)).toBeNull();
  });
});

describe('IncidentViewPage - CP-28C pressure progression', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-pressure');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: pressureIncident() } as never);
  });

  it('shows a pressure hero when pressure signals are present', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('The conversation is becoming more pressuring.')).toBeDefined();
    });
  });

  it('shows the pressure story with every stage LUMINA recorded', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('How the Pressure Built')).toBeDefined();
    });
    expect(screen.getByText('Authority claim')).toBeDefined();
    expect(screen.getByText('Pressure')).toBeDefined();
    expect(screen.getByText('Request')).toBeDefined();
    expect(screen.getByText('Escalation')).toBeDefined();
    expect(screen.getByText('LUMINA identified a pattern of increasing pressure.')).toBeDefined();
  });

  it('only shows stages that were actually recorded', async () => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: defaultIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('How the Pressure Built')).toBeDefined();
    });
    expect(screen.getByText('Request')).toBeDefined();
    expect(screen.queryByText('Authority claim')).toBeNull();
    expect(screen.queryByText('Pressure')).toBeNull();
    expect(screen.queryByText('Escalation')).toBeNull();
  });
});

// ---- CP-28C: trusted human connection ----

describe('IncidentViewPage - CP-28C trusted human connection', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: defaultIncident() } as never);
    vi.mocked(getTrustedContact).mockReset();
    vi.mocked(getTrustedContact).mockResolvedValue({ configured: false, contact: null });
  });

  it('leads with the trusted-human message', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText("You don't have to handle this alone.")).toBeDefined();
    });
  });

  it('is honest when no trusted contact is configured', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('No trusted contact is configured yet.')).toBeDefined();
    });
    expect(screen.getByRole('button', { name: /set up a trusted contact/i })).toBeDefined();
  });

  it('shows a configured contact without revealing the full destination', async () => {
    vi.mocked(getTrustedContact).mockResolvedValue({
      configured: true,
      contact: {
        contact_id: 'tc-1',
        display_name: 'Mina',
        delivery_channel: 'SMS',
        enabled: true,
        automatic_help_enabled: true,
        configured_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        destination_masked: '•••• 9988',
      },
    });

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Mina')).toBeDefined();
    });
    expect(screen.getByText(/•••• 9988/)).toBeDefined();
    expect(screen.getByText(/automatic help is on/i)).toBeDefined();
    expect(screen.queryByText(/555 000 0000/)).toBeNull();
  });
});

// ---- CP-28C: honest help states ----

describe('IncidentViewPage - CP-28C honest help states', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-123');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: defaultIncident() } as never);
    vi.mocked(requestHelp).mockReset();
    vi.mocked(requestHelp).mockResolvedValue({
      incident_id: 'test-incident-123',
      help_story: {
        incident_id: 'test-incident-123',
        generated_at: '2024-01-01T00:01:00Z',
        urgency: 'HIGH',
        one_line_summary: 'A verification code was requested during a call.',
        sections: [],
        privacy_note: 'This summary is shown only to your trusted contact.',
      },
      help_story_text: '',
      already_requested: false,
      trusted_contact_notified: false,
      delivery_status: 'DELIVERED',
      trusted_contact_configured: true,
      delivery_channel: 'SMS',
    });
  });

  it('requests help through the real endpoint with the incident id', async () => {
    renderWithRouter(<IncidentViewPage />);
    const button = await screen.findByRole('button', { name: /I'M TRAPPED/i });
    fireEvent.click(button);
    await waitFor(() => {
      expect(requestHelp).toHaveBeenCalledTimes(1);
      expect(requestHelp).toHaveBeenCalledWith('test-incident-123');
    });
  });

  it('shows confirmed delivery only when the backend says DELIVERED', async () => {
    renderWithRouter(<IncidentViewPage />);
    const button = await screen.findByRole('button', { name: /I'M TRAPPED/i });
    fireEvent.click(button);
    await waitFor(() => {
      expect(screen.getByText('Your trusted contact received your help request.')).toBeDefined();
    });
  });

  it('never presents NOT_CONFIGURED as a success', async () => {
    vi.mocked(requestHelp).mockResolvedValue({
      incident_id: 'test-incident-123',
      help_story: {
        incident_id: 'test-incident-123',
        generated_at: '2024-01-01T00:01:00Z',
        urgency: 'HIGH',
        one_line_summary: 'A verification code was requested during a call.',
        sections: [],
        privacy_note: 'This summary is shown only to your trusted contact.',
      },
      help_story_text: '',
      already_requested: false,
      trusted_contact_notified: false,
      delivery_status: 'NOT_CONFIGURED',
      trusted_contact_configured: false,
      delivery_channel: 'NONE',
    });

    renderWithRouter(<IncidentViewPage />);
    const button = await screen.findByRole('button', { name: /I'M TRAPPED/i });
    fireEvent.click(button);
    await waitFor(() => {
      expect(screen.getByText(/A trusted contact is required for automatic delivery/i)).toBeDefined();
    });
    expect(screen.queryByText(/received your help request/i)).toBeNull();
  });
});

// ---- CP-28C: conversation centerpiece & claim vs confirmation ----

describe('IncidentViewPage - CP-28C conversation centerpiece', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-conv');
    vi.mocked(getIncident).mockReset();
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: conversationIncident() } as never);
  });

  it('attributes quoted speech to Caller, You, or Speaker unclear', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Caller')).toBeDefined();
    });
    expect(screen.getByText('You')).toBeDefined();
    expect(screen.getByText('Speaker unclear')).toBeDefined();
    expect(screen.getByText(/Give me your OTP/)).toBeDefined();
    expect(screen.getByText(/I need it right now/)).toBeDefined();
  });

  it('honestly explains that the record only reflects what the user added', async () => {
    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Conversation$/i })).toBeDefined();
    });
    expect(screen.getAllByText(/only sees what you add yourself/i).length).toBeGreaterThan(0);
  });
});

describe('IncidentViewPage - CP-28C claim vs confirmed', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.mocked(getIncident).mockReset();
  });

  it('shows a claim as unconfirmed until the user agrees', async () => {
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-claim');
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: claimedIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Did You Already Act?')).toBeDefined();
    });
    expect(screen.getByRole('button', { name: /I shared an OTP or verification code/i })).toBeDefined();
    expect(screen.queryByText('What You Confirmed')).toBeNull();
  });

  it('labels explicitly confirmed actions as confirmed', async () => {
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-confirmed');
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: confirmedIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What You Confirmed')).toBeDefined();
    });
    expect(screen.getByText('I shared an OTP or verification code')).toBeDefined();
    expect(screen.getByText('You confirmed this happened.')).toBeDefined();
    expect(screen.queryByText('Did You Already Act?')).toBeNull();
  });
});

// ---- CP-29: LUMINA Guidance (deterministic intervention) ----

// Mirrors a backend decision stored in incident.metadata["intervention"].
function interventionDecision(
  overrides: Partial<InterventionDecision> = {},
): InterventionDecision {
  return {
    intervention_id: 'int-1',
    incident_id: 'test-incident-int',
    intervention_level: 'PAUSE',
    intervention_type: 'PAUSE_AND_REVIEW',
    reason: 'The caller is applying time pressure before asking for the code.',
    supporting_evidence_ids: ['entry-2'],
    next_action: 'Verify the request independently.',
    trusted_help_recommended: false,
    auto_help_eligible: false,
    trigger_stage: 'PRESSURE',
    epistemic_status: 'DETERMINISTIC',
    is_new: true,
    created_at: '2024-01-01T00:01:00Z',
    ...overrides,
  };
}

function interventionIncident(decision: InterventionDecision | null) {
  const base = defaultIncident();
  return {
    ...base,
    incident_id: 'test-incident-int',
    // The backend stores the decision at incident.metadata["intervention"].
    metadata: decision ? { intervention: decision } : {},
  };
}

describe('IncidentViewPage - CP-29 LUMINA Guidance intervention', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-int');
    vi.mocked(getIncident).mockReset();
  });

  it('hides the guidance section when no intervention decision exists', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: interventionIncident(null) } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText(/Do not share the OTP/)).toBeDefined();
    });
    expect(screen.queryByText('LUMINA Guidance')).toBeNull();
  });

  it('renders calm guidance when an intervention decision exists', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(
        interventionDecision({
          reason: 'The conversation includes an OTP request that should be checked before sharing anything.',
        }),
      ),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'LUMINA Guidance' })).toBeDefined();
    });
    expect(
      screen.getByText('The conversation includes an OTP request that should be checked before sharing anything.'),
    ).toBeDefined();
  });

  it('leads with level-specific calm copy', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision({ intervention_level: 'URGENT' })),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText("Don't share anything else yet.")).toBeDefined();
    });
  });

  it('does not repeat the raw next-action text in the guidance section', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision()),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    // The guidance never echoes Next Safe Action's verbatim action string.
    expect(screen.queryByText('Verify the request independently.')).toBeNull();
  });

  it('anchors to the next safe action and the conversation', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision()),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.getByRole('link', { name: 'See your next safe step' }).getAttribute('href')).toBe('#next-action');
    expect(screen.getByRole('link', { name: 'Review the conversation' }).getAttribute('href')).toBe('#conversation');
  });

  it('offers trusted-human help only when recommended or at HELP level', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision({ trusted_help_recommended: true })),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.getByRole('link', { name: 'Connect with your trusted human' }).getAttribute('href')).toBe('#trusted-human');
  });

  it('shows the ask-for-help anchor only at the HELP level', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(
        interventionDecision({
          intervention_level: 'HELP',
          intervention_type: 'REQUEST_TRUSTED_HELP',
          trusted_help_recommended: true,
          auto_help_eligible: true,
        }),
      ),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.getByRole('link', { name: 'Ask for help now' })).toBeDefined();
    expect(screen.getByRole('link', { name: 'Connect with your trusted human' })).toBeDefined();
  });

  it('keeps the pre-Help level from claiming urgent assistance', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision({ intervention_level: 'ATTENTION' })),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.queryByRole('link', { name: 'Ask for help now' })).toBeNull();
  });

  it('uses the honest why-label for the decision level', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(
        interventionDecision({
          intervention_level: 'URGENT',
          reason: 'A caller combined authority claims with a direct request for the code.',
        }),
      ),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.getByText('Why LUMINA is asking you to be careful:')).toBeDefined();
    expect(screen.getByText('A caller combined authority claims with a direct request for the code.')).toBeDefined();
  });

  it('never surfaces numeric confidence or risk scores in the guidance', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision()),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.queryByText(/risk score/i)).toBeNull();
    expect(screen.queryByText(/scam probability/i)).toBeNull();
    expect(screen.queryByText(/\bconfidence\b/i)).toBeNull();
    expect(screen.queryByText(/\d+% chance/i)).toBeNull();
  });

  it('keeps the live masthead conversation-centered when guidance is shown', async () => {
    vi.mocked(getIncident).mockResolvedValue({
      ok: true,
      data: interventionIncident(interventionDecision()),
    } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('LUMINA Guidance')).toBeDefined();
    });
    expect(screen.getByRole('heading', { name: /^Conversation$/i })).toBeDefined();
  });
});

// ---- CP-30: Recovery & Continuity ----

// Mirrors the deterministic snapshot the backend stores at
// incident.metadata["recovery"] (see app/incident/recovery.py). Confirmed
// actions carry SANITIZED labels, never raw secrets.
function recoverySnapshot(overrides: Record<string, unknown> = {}) {
  return {
    incident_id: 'test-incident-recovery',
    phase: 'AFTER_DAMAGE',
    short_description:
      'You confirmed a verification code was shared. Recovery and reporting are in progress.',
    confirmed_actions: [
      {
        action_id: 'usr-action-1',
        action_type: 'SHARED_CODE',
        description: 'A verification code was shared',
      },
    ],
    help_requested: true,
    tasks: [
      {
        task_id: 'recovery-contain-financial',
        incident_id: 'test-incident-recovery',
        category: 'CONTAIN',
        title: 'Change the password on the account tied to the shared code',
        description:
          'Sign in to that account and set a password you have not used anywhere else.',
        priority: 'HIGH',
        status: 'COMPLETED',
        reason: 'Confirmed by a step you took in this incident',
        evidence_ids: [],
        created_at: '2024-01-01T00:02:00Z',
        completed_at: '2024-01-01T00:03:00Z',
      },
      {
        task_id: 'recovery-secure-authentication',
        incident_id: 'test-incident-recovery',
        category: 'SECURE',
        title: 'Ask the provider to require a second step to sign in',
        description:
          'Enable an authenticator app or a security key on the affected account.',
        priority: 'HIGH',
        status: 'IN_PROGRESS',
        reason: 'LUMINA has no evidence this step happened yet',
        evidence_ids: [],
        created_at: '2024-01-01T00:02:00Z',
        completed_at: null,
      },
      {
        task_id: 'recovery-report-financial',
        incident_id: 'test-incident-recovery',
        category: 'REPORT',
        title: 'Tell the provider that the account may have been taken over',
        description:
          'Contact the account provider using a number or app you trust.',
        priority: 'HIGH',
        status: 'NOT_STARTED',
        reason: 'This step has not been confirmed in this incident',
        evidence_ids: [],
        created_at: '2024-01-01T00:02:00Z',
        completed_at: null,
      },
      {
        task_id: 'recovery-monitor-identity',
        incident_id: 'test-incident-recovery',
        category: 'MONITOR',
        title: 'Watch the account for anything you did not do',
        description:
          'Keep an eye on sign-ins and messages for the next few weeks.',
        priority: 'MEDIUM',
        status: 'NOT_VERIFIED',
        reason: 'LUMINA cannot check your accounts for you',
        evidence_ids: [],
        created_at: '2024-01-01T00:02:00Z',
        completed_at: null,
      },
      {
        task_id: 'recovery-preserve-evidence',
        incident_id: 'test-incident-recovery',
        category: 'PRESERVE',
        title: 'Keep the evidence for this incident',
        description:
          'The conversation and the summary stay saved in this record.',
        priority: 'LOW',
        status: 'COMPLETED',
        reason: 'This incident record is preserved automatically',
        evidence_ids: [],
        created_at: '2024-01-01T00:02:00Z',
        completed_at: '2024-01-01T00:02:00Z',
      },
    ],
    stages: [
      { stage: 'CONTAIN', status: 'COMPLETED', priority: 'HIGH', task_ids: ['recovery-contain-financial'] },
      { stage: 'SECURE', status: 'IN_PROGRESS', priority: 'HIGH', task_ids: ['recovery-secure-authentication'] },
      { stage: 'PRESERVE', status: 'COMPLETED', priority: 'LOW', task_ids: ['recovery-preserve-evidence'] },
      { stage: 'REPORT', status: 'IN_PROGRESS', priority: 'HIGH', task_ids: ['recovery-report-financial'] },
      { stage: 'RECOVER', status: 'UNKNOWN', priority: 'NONE', task_ids: [] },
      { stage: 'MONITOR', status: 'IN_PROGRESS', priority: 'MEDIUM', task_ids: ['recovery-monitor-identity'] },
    ],
    monitoring_note:
      'LUMINA cannot check your bank, your device, or your identity for you. Keep checking the affected accounts yourself.',
    created_at: '2024-01-01T00:02:00Z',
    updated_at: '2024-01-01T00:02:00Z',
    ...overrides,
  };
}

function recoveringIncident() {
  const base = defaultIncident();
  return {
    ...base,
    incident_id: 'test-incident-recovery',
    status: 'RECOVERING',
    next_action: {
      action: 'Change the password on the account tied to the shared code.',
      reason: 'You confirmed a verification code was shared.',
      evidence_basis: ['Confirmed by you in this incident'],
      urgency: 'IMMEDIATE',
    },
    metadata: { recovery: recoverySnapshot() },
  };
}

function preDamageIncident() {
  const base = defaultIncident();
  return {
    ...base,
    incident_id: 'test-incident-predamage',
    status: 'ACTION_REQUIRED',
    metadata: {
      recovery: recoverySnapshot({ phase: 'BEFORE_DAMAGE' }),
    },
  };
}

describe('IncidentViewPage - CP-30 Recovery & Continuity', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('lumina_current_incident_id', 'test-incident-recovery');
    vi.mocked(getIncident).mockReset();
  });

  it('relabels the hero from prevention to recovery after a confirmed step', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Recovery & Continuity' })).toBeDefined();
    });
    expect(screen.getByRole('heading', { name: 'Next Recovery Action' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Next Safe Action' })).toBeNull();
  });

  it('shows what was confirmed with the user, sanitized, never raw secrets', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Recovery & Continuity')).toBeDefined();
    });
    expect(screen.getByText('What you\'ve already done')).toBeDefined();
    // The sanitized label from the backend, not any shared secret.
    expect(screen.getByText('A verification code was shared')).toBeDefined();
    expect(screen.getByText('You asked a trusted person for help.')).toBeDefined();
    expect(screen.queryByText(/987654/i)).toBeNull();
  });

  it('shows preserved record items under what was done', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Recovery & Continuity')).toBeDefined();
    });
    expect(screen.getByText(/Keep the evidence for this incident — preserved in this record/i)).toBeDefined();
  });

  it('shows recovery stages with honest status words, not scores', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Recovery & Continuity')).toBeDefined();
    });
    expect(screen.getByText('Where things stand')).toBeDefined();
    expect(screen.getByText('Contain')).toBeDefined();
    expect(screen.getAllByText('Complete').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('In progress').length).toBeGreaterThanOrEqual(2);
    // No numeric bar, no percentages — just stage words.
    expect(screen.getByText('These are stages, not a progress bar. Each one reports only what the incident record can confirm.')).toBeDefined();
    expect(screen.queryByText(/\d+%/i)).toBeNull();
    expect(screen.queryByText(/risk score/i)).toBeNull();
  });

  it('shows what still needs attention with honest task statuses', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('What still needs attention')).toBeDefined();
    });
    expect(screen.getByText('Not started')).toBeDefined();
    expect(screen.getByText("LUMINA can't verify yet")).toBeDefined();
    expect(screen.getByText(/LUMINA has no evidence this step happened/i)).toBeDefined();
    // Nothing unanswered is labelled complete.
    expect(screen.queryByText(/Tell the provider that the account may have been taken over — preserved in this record/i)).toBeNull();
  });

  it('shows the monitoring note and the honest boundary of LUMINA', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Recovery & Continuity')).toBeDefined();
    });
    expect(screen.getByText(/LUMINA cannot check your bank, your device, or your identity for you/)).toBeDefined();
    expect(screen.getByText(/LUMINA cannot perform these steps for you/)).toBeDefined();
  });

  it('keeps the conversation masthead centered during recovery', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: recoveringIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText('Recovery & Continuity')).toBeDefined();
    });
    expect(screen.getByRole('heading', { name: /^Conversation$/i })).toBeDefined();
  });

  it('stays in prevention mode before any damage is confirmed', async () => {
    vi.mocked(getIncident).mockResolvedValue({ ok: true, data: preDamageIncident() } as never);

    renderWithRouter(<IncidentViewPage />);
    await waitFor(() => {
      expect(screen.getByText(/Do not share the OTP/)).toBeDefined();
    });
    expect(screen.getByRole('heading', { name: 'Next Safe Action' })).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Next Recovery Action' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Recovery & Continuity' })).toBeNull();
  });
});
