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
