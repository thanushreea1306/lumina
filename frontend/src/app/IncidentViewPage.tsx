/* ============================================================
   LUMINA Incident View Page — Live Incident Centerpiece
   ============================================================
   First viewport answers, in order:
     1. WHAT IS HAPPENING?     → LIVE INCIDENT masthead + hero state
     2. WHAT SHOULD I DO NOW?  → Next Safe Action (visually dominant)
     3. CAN I GET HELP?        → I'M TRAPPED — GET HELP
   Then: CONVERSATION → PRESSURE STORY → trusted human connection →
   WHAT MAY BE AT RISK → WHAT WE KNOW / WHAT WE DON'T KNOW →
   confirmations → details (evidence entry, audio analysis, and
   technical analysis behind a disclosure).

   Rules honored (CP-28C):
   - No frontend safety decisions, no scam scores, no confidence
     percentages, no fabricated transcripts, no fabricated contacts.
     Only backend-persisted evidence is shown.
   - Hero states derive from real backend data: status first, then
     recorded pressure signals, then any recorded evidence. CALM is
     only offered when nothing concerning was recorded.
   - Pressure progression shows only the stages LUMINA actually
     recorded, and is never presented as proof of who is on the
     other side.
   - Help delivery states are honest: DELIVERED only when the backend
     confirms delivery; NOT_CONFIGURED is never shown as a success.
   - Copy is honest about audio: LUMINA never records calls without
     asking, never intercepts calls, and never runs in the background.
   - Engineering terms live only inside the Technical Analysis
     disclosure at the end.
   ============================================================ */

import { useState, useCallback, useEffect, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useIncidentState, INCIDENT_STATUS_LABELS, INCIDENT_PRIORITY_LABELS } from '@/hooks/useIncidentState';
import { useStreamingSession } from '@/hooks/useStreamingSession';
import { uploadIncidentAudio } from '@/lib/api/incidents';
import { requestHelp } from '@/lib/api/help';
import { getTrustedContact, type GetTrustedContactResponse } from '@/lib/api/account';
import { ensureDeviceIdentity } from '@/lib/api/device';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import type {
  IncidentStatus,
  Priority,
  ExposureCategory,
  ExposureLevel,
  TimelineEntry,
  TranscriptSource,
  TranscriptSegment,
  UploadAudioResponse,
  EscalationResult,
  HelpStory,
  ConversationIntelligenceResult,
  MLIntelligenceResult,
  InterventionDecision,
  RecoverySnapshot,
  RecoveryStage,
} from '@/types/incident';

// ---- Human-readable labels ----

const EXPOSURE_CATEGORY_LABELS: Record<ExposureCategory, string> = {
  MONEY: 'Money',
  ACCOUNT: 'Account',
  AUTHENTICATION: 'Authentication',
  DEVICE: 'Device',
  IDENTITY: 'Identity',
  PERSONAL_INFORMATION: 'Personal information',
  UNKNOWN: 'Unknown',
};

const EXPOSURE_LEVEL_LABELS: Record<ExposureLevel, string> = {
  NOT_INDICATED: 'No confirmed exposure',
  POTENTIALLY_EXPOSED: 'Potentially exposed',
  USER_CONFIRMED_EXPOSED: 'Confirmed exposed',
  UNKNOWN: 'Unknown',
};

const OBSERVATION_LABELS: Record<string, string> = {
  AUTHORITY_CLAIM: 'Someone claimed to represent an authority',
  THREAT_OF_ARREST: 'Threat of arrest was made',
  THREAT_OF_LEGAL_ACTION: 'Threat of legal action was made',
  URGENCY: 'Urgency or time pressure was applied',
  SECRECY_REQUEST: 'Secrecy was requested',
  MONEY_REQUEST: 'Money was requested',
  OTP_REQUEST: 'A verification code was requested',
  PASSWORD_REQUEST: 'A password was requested',
  IDENTITY_DOCUMENT_REQUEST: 'Identity documents were requested',
  REMOTE_ACCESS_REQUEST: 'Remote access was requested',
  APP_INSTALL_REQUEST: 'App installation was requested',
  BANK_TRANSFER_REQUEST: 'A bank transfer was requested',
  CRYPTO_REQUEST: 'Cryptocurrency transfer was requested',
  GIFT_CARD_REQUEST: 'Gift card purchase was requested',
  CALL_BACK_INSTRUCTION: 'Callback to a specific number was instructed',
  INDEPENDENT_VERIFICATION_BLOCKED: 'Independent verification was blocked',
};

// Labels for confirmed/confirmable user actions. These describe an action
// the user may have taken; confirmation is always an explicit user choice.
const ACTION_TYPE_LABELS: Record<string, string> = {
  SHARED_OTP: 'I shared an OTP or verification code',
  SHARED_PASSWORD: 'I shared a password',
  SHARED_PERSONAL_INFORMATION: 'I shared personal information',
  SHARED_DOCUMENT: 'I shared an identity document',
  SENT_MONEY: 'I sent money or made a transfer',
  CLICKED_LINK: 'I clicked a link',
  INSTALLED_APPLICATION: 'I installed an application',
  GRANTED_REMOTE_ACCESS: 'I granted remote access',
  LOGGED_IN: 'I logged in to an account',
  DECLINED_REQUEST: 'I did not act on the request',
  UNKNOWN_ACTION: 'I took an action but the details are unclear',
};

const ESCALATION_STAGE_LABELS: Record<string, string> = {
  SETUP: 'Setup',
  PRESSURE: 'Pressure',
  EXTRACTION: 'Extraction',
};

// ---- Recovery board labels (CP-30) ----
// Human words for the deterministic recovery snapshot. These labels are the
// honest, plain-language rendering of RecoveryStage/RecoveryTaskStatus — they
// never add completion that the backend did not confirm.

const RECOVERY_STAGE_LABELS: Record<RecoveryStage, string> = {
  CONTAIN: 'Contain',
  SECURE: 'Secure',
  PRESERVE: 'Preserve',
  REPORT: 'Report',
  RECOVER: 'Recover',
  MONITOR: 'Monitor',
};

const RECOVERY_STAGE_STATUS_LABELS: Record<string, string> = {
  NOT_APPLICABLE: "Doesn't apply",
  COMPLETED: 'Complete',
  IN_PROGRESS: 'In progress',
  UNKNOWN: "Can't verify yet",
};

const RECOVERY_TASK_STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: 'Not started',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Complete',
  NOT_AVAILABLE: 'Not available',
  NOT_VERIFIED: "LUMINA can't verify yet",
  NOT_APPLICABLE: "Doesn't apply",
  UNKNOWN: 'Unknown',
};

const RECOVERY_TASK_STATUS_CLASS: Record<string, string> = {
  NOT_STARTED: 'incident-recovery-task--attention',
  IN_PROGRESS: 'incident-recovery-task--attention',
  COMPLETED: 'incident-recovery-task--done',
  NOT_AVAILABLE: 'incident-recovery-task--muted',
  NOT_VERIFIED: 'incident-recovery-task--muted',
  NOT_APPLICABLE: 'incident-recovery-task--muted',
  UNKNOWN: 'incident-recovery-task--attention',
};

// ---- Intervention guidance copy (CP-29) ----
// Static, calm, evidence-grounded. The paragraph text comes from the backend
// decision; these labels only frame it. Never repeats Next Safe Action's
// verbatim action text.

const INTERVENTION_LEAD_COPY: Record<string, string> = {
  ATTENTION: 'Take a moment to review what is being asked.',
  PAUSE: 'Pause before you continue.',
  URGENT: "Don't share anything else yet.",
  HELP: 'A trusted person can help you through this.',
};

const INTERVENTION_WHY_LABEL: Record<string, string> = {
  ATTENTION: 'Why LUMINA is watching:',
  PAUSE: 'Why LUMINA is asking you to pause:',
  URGENT: 'Why LUMINA is asking you to be careful:',
  HELP: 'Why LUMINA is recommending trusted help:',
};

const INTERVENTION_CLASS: Record<string, string> = {
  ATTENTION: 'incident-intervention--attention',
  PAUSE: 'incident-intervention--pause',
  URGENT: 'incident-intervention--urgent',
  HELP: 'incident-intervention--help',
};

// ---- Hero states (CP-28C) ----
// Derived from backend data only. Status wins; otherwise pressure signals,
// then any recorded evidence; CALM only when nothing concerning exists.

type HeroState =
  | 'CALM'
  | 'ATTENTION'
  | 'PRESSURE'
  | 'ACTION_REQUIRED'
  | 'RECOVERING'
  | 'CLOSED'
  | 'UNKNOWN';

const HERO_STATE_COPY: Record<HeroState, { lead: string; chip?: string; className: string }> = {
  CALM: {
    lead: 'LUMINA is watching this conversation. Nothing concerning has been recorded yet.',
    chip: 'Calm',
    className: 'incident-masthead--calm',
  },
  ATTENTION: {
    lead: 'Something about this conversation needs your attention.',
    chip: 'Worth attention',
    className: 'incident-masthead--attention',
  },
  PRESSURE: {
    lead: 'The conversation is becoming more pressuring.',
    chip: 'Pressure building',
    className: 'incident-masthead--pressure',
  },
  ACTION_REQUIRED: {
    lead: 'The situation needs a decision from you.',
    chip: 'Needs a decision',
    className: 'incident-masthead--action_required',
  },
  RECOVERING: {
    lead: 'This incident is in recovery. LUMINA is tracking the steps taken so far.',
    chip: 'Recovering',
    className: 'incident-masthead--recovering',
  },
  CLOSED: {
    lead: 'This incident is closed. What follows is the record for your files.',
    className: 'incident-masthead--closed',
  },
  UNKNOWN: {
    lead: 'The current state of this incident is unclear.',
    chip: 'State unclear',
    className: 'incident-masthead--unknown',
  },
};

const HERO_CHIP_CLASS: Record<HeroState, string | null> = {
  CALM: 'incident-hero-chip--calm',
  ATTENTION: 'incident-hero-chip--attention',
  PRESSURE: 'incident-hero-chip--pressure',
  ACTION_REQUIRED: 'incident-hero-chip--action_required',
  RECOVERING: 'incident-hero-chip--recovering',
  CLOSED: null,
  UNKNOWN: 'incident-hero-chip--unknown',
};

// ---- Pressure progression signal sets (CP-28C) ----
// Stage gating is evidence-grounded: a stage renders only when at least
// one recorded observation of that kind exists.

const AUTHORITY_OBSERVATION_TYPES = new Set([
  'AUTHORITY_CLAIM',
  'THREAT_OF_ARREST',
  'THREAT_OF_LEGAL_ACTION',
]);

const PRESSURE_OBSERVATION_TYPES = new Set([
  'URGENCY',
  'SECRECY_REQUEST',
]);

const REQUEST_OBSERVATION_TYPES = new Set([
  'MONEY_REQUEST',
  'OTP_REQUEST',
  'PASSWORD_REQUEST',
  'IDENTITY_DOCUMENT_REQUEST',
  'REMOTE_ACCESS_REQUEST',
  'APP_INSTALL_REQUEST',
  'BANK_TRANSFER_REQUEST',
  'CRYPTO_REQUEST',
  'GIFT_CARD_REQUEST',
]);

// ---- Visual mapping: status / priority / level → CSS classes ----

const STATUS_CLASS: Record<IncidentStatus, string> = {
  ACTIVE: 'incident-status--active',
  MONITORING: 'incident-status--monitoring',
  ACTION_REQUIRED: 'incident-status--action_required',
  RECOVERING: 'incident-status--recovering',
  CLOSED: 'incident-status--closed',
  UNKNOWN: 'incident-status--unknown',
};

const ACTION_CLASS: Record<Priority, string> = {
  IMMEDIATE: 'incident-action-hero--immediate',
  HIGH: 'incident-action-hero--high',
  MEDIUM: 'incident-action-hero--medium',
  LOW: 'incident-action-hero--low',
  NONE: 'incident-action-hero--none',
};

const RISK_LEVEL_CLASS: Record<ExposureLevel, string> = {
  NOT_INDICATED: 'incident-risk-level--none',
  POTENTIALLY_EXPOSED: 'incident-risk-level--potential',
  USER_CONFIRMED_EXPOSED: 'incident-risk-level--exposed',
  UNKNOWN: 'incident-risk-level--unknown',
};

const STAGE_CHIP_CLASS: Record<string, string> = {
  SETUP: 'incident-chip--system',
  PRESSURE: 'incident-chip--warning',
  EXTRACTION: 'incident-chip--danger',
};

// ---- Timeline / conversation formatting ----

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function formatDateTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return '';
  }
}

// ---- Local section wrapper ----
// Replaces Card (which hard-codes role="region") with a landmark
// `<section>` named by its heading — the semantically correct pattern.

function IncidentSection({
  id,
  eyebrow,
  title,
  subtitle,
  children,
  className,
}: {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  const headingId = `${id}-title`;
  return (
    <section
      id={id}
      className={`incident-section${className ? ` ${className}` : ''}`}
      aria-labelledby={headingId}
    >
      <span className="incident-eyebrow">{eyebrow}</span>
      <h2 id={headingId} className="incident-h2">{title}</h2>
      {subtitle && <p className="incident-subtitle">{subtitle}</p>}
      <div className="incident-section-body">{children}</div>
    </section>
  );
}

// ---- Conversation item (persisted incident timeline entry) ----
// Speaker attribution is honest: Caller, You, or a clear "unclear" badge.
// LUMINA never guesses a speaker it cannot attribute.

const TIMELINE_TYPE_LABELS: Record<string, string> = {
  INCIDENT_CREATED: 'Incident started',
  EVIDENCE_ADDED: 'Evidence identified',
  USER_ACTION_RECORDED: 'User action recorded',
  STATE_CHANGED: 'Status changed',
  EXPOSURE_UPDATED: 'Exposure updated',
  INCIDENT_CLOSED: 'Incident closed',
};

function ConversationItem({ entry }: { entry: TimelineEntry }) {
  const time = formatTimestamp(entry.timestamp);
  const label = TIMELINE_TYPE_LABELS[entry.entry_type] ?? entry.entry_type;
  const textSpan = entry.metadata?.text_span;
  const startTime = entry.metadata?.segment_start_time;
  const endTime = entry.metadata?.segment_end_time;
  const speaker = entry.metadata?.speaker as string | undefined;

  return (
    <div className="incident-conv-item">
      <span aria-hidden="true" className="incident-conv-dot" />
      <div className="incident-conv-meta">
        {time && <span className="incident-conv-time">{time}</span>}
        {speaker === 'CALLER' && (
          <span className="incident-conv-badge incident-conv-badge--caller">Caller</span>
        )}
        {speaker === 'USER' && (
          <span className="incident-conv-badge incident-conv-badge--user">You</span>
        )}
        {speaker && speaker !== 'CALLER' && speaker !== 'USER' && (
          <span className="incident-conv-badge incident-conv-badge--unknown">Speaker unclear</span>
        )}
      </div>
      <div className="incident-conv-type-row">
        <span className="incident-conv-type">{label}</span>
        {typeof startTime === 'number' && (
          <span className="incident-conv-time">
            {startTime.toFixed(1)}s
            {typeof endTime === 'number' && <> – {endTime.toFixed(1)}s</>}
          </span>
        )}
      </div>
      {entry.summary && <p className="incident-conv-summary">{entry.summary}</p>}
      {typeof textSpan === 'string' && textSpan && (
        <div className="incident-conv-quote">&ldquo;{textSpan}&rdquo;</div>
      )}
    </div>
  );
}

// ---- Recovery board (CP-30) ----
// Rendered only for AFTER_DAMAGE incidents: what happened, what has been
// done, what is still open. Every line is backend-derived. No completion is
// ever implied without evidence, and no numeric progress is shown.

function RecoveryBoard({ recovery, isClosed }: { recovery: RecoverySnapshot; isClosed: boolean }) {
  const doneActions = recovery.confirmed_actions;
  const outstandingTasks = recovery.tasks.filter(
    (t) => t.status !== 'COMPLETED',
  );
  const preservedTasks = recovery.tasks.filter(
    (t) => t.status === 'COMPLETED',
  );

  return (
    <div className="incident-recovery-board">
      <p className="incident-recovery-lead">
        {isClosed
          ? 'This incident is closed. The recovery record below is kept for your files.'
          : 'A step in this incident has been confirmed. LUMINA marks a step complete only when there is evidence of it.'}
      </p>

      {doneActions.length > 0 && (
        <div className="incident-recovery-block">
          <span className="incident-eyebrow">Confirmed with you</span>
          <h3 className="incident-h3">What you've already done</h3>
          <ul className="incident-recovery-done-list">
            {doneActions.map((a) => (
              <li key={a.action_id}>{a.description}</li>
            ))}
            {recovery.help_requested && (
              <li>You asked a trusted person for help.</li>
            )}
            {preservedTasks.map((t) => (
              <li key={t.task_id}>{t.title} — preserved in this record.</li>
            ))}
          </ul>
        </div>
      )}

      <div className="incident-recovery-block">
        <span className="incident-eyebrow">Recovery progress</span>
        <h3 className="incident-h3">Where things stand</h3>
        <div className="incident-recovery-stages" role="list">
          {recovery.stages.map((stage) => (
            <div
              key={stage.stage}
              role="listitem"
              className="incident-recovery-stage"
            >
              <span
                aria-hidden="true"
                className={`incident-recovery-stage-dot incident-recovery-stage-dot--${stage.status.toLowerCase()}`}
              />
              <span className="incident-recovery-stage-name">
                {RECOVERY_STAGE_LABELS[stage.stage]}
              </span>
              <span className="incident-recovery-stage-status">
                {RECOVERY_STAGE_STATUS_LABELS[stage.status] ?? stage.status}
              </span>
            </div>
          ))}
        </div>
        <p className="incident-note" style={{ marginTop: 'var(--space-2)' }}>
          These are stages, not a progress bar. Each one reports only what the
          incident record can confirm.
        </p>
      </div>

      {outstandingTasks.length > 0 && (
        <div className="incident-recovery-block">
          <span className="incident-eyebrow">Still open</span>
          <h3 className="incident-h3">What still needs attention</h3>
          <div className="incident-stack">
            {outstandingTasks.map((task) => (
              <div key={task.task_id} className={`incident-recovery-task ${RECOVERY_TASK_STATUS_CLASS[task.status] ?? ''}`}>
                <div className="incident-recovery-task-title">{task.title}</div>
                <p className="incident-recovery-task-desc">{task.description}</p>
                <div className="incident-conv-meta" style={{ marginTop: 'var(--space-2)' }}>
                  <span className={`incident-chip incident-chip--trial ${
                    task.status === 'NOT_AVAILABLE' || task.status === 'NOT_VERIFIED'
                      ? 'incident-chip--muted'
                      : 'incident-chip--warning'
                  }`}>
                    {RECOVERY_TASK_STATUS_LABELS[task.status] ?? task.status}
                  </span>
                  <span className="incident-recovery-task-reason">{task.reason}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {recovery.monitoring_note && (
        <div role="status" className="incident-recovery-monitoring">
          <span aria-hidden="true">◉</span>
          {recovery.monitoring_note}
        </div>
      )}

      <p className="incident-note">
        LUMINA cannot perform these steps for you — contacting your bank,
        filing reports, securing accounts, or monitoring your accounts are
        actions only you and the official provider can take.
      </p>
    </div>
  );
}

// ---- Main Component ----

export function IncidentViewPage() {
  const [searchParams] = useSearchParams();
  const overrideIncidentId = searchParams.get('id');

  const {
    status,
    incident,
    error,
    errorCode,
    lastExtraction,
    submitTranscript,
    confirmAction,
    refresh,
    endIncident,
    closing,
    closeError,
  } = useIncidentState(30_000, overrideIncidentId);

  const [transcriptText, setTranscriptText] = useState('');
  const [transcriptSource, setTranscriptSource] = useState<TranscriptSource>('USER_TYPED');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showProvenance, setShowProvenance] = useState<Record<string, boolean>>({});

  // ---- Audio upload state ----
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadAudioResponse | null>(null);
  const [uploadedSegments, setUploadedSegments] = useState<TranscriptSegment[]>([]);

  // ---- Streaming session state (CP-15) ----
  const streaming = useStreamingSession(incident?.incident_id ?? '');

  // ---- Help request state (CP-17) ----
  const [helpRequesting, setHelpRequesting] = useState(false);
  const [helpStory, setHelpStory] = useState<HelpStory | null>(null);
  const [helpError, setHelpError] = useState<string | null>(null);
  const [helpDeliveryStatus, setHelpDeliveryStatus] = useState<string | null>(null);
  const [helpConfigured, setHelpConfigured] = useState<boolean | null>(null);

  // ---- Trusted human connection state (CP-28C) ----
  // Read-only lookup of the real configured trusted contact. The backend
  // redacts the destination; the client can never invent a contact.
  const [trustedContactStatus, setTrustedContactStatus] = useState<'loading' | 'configured' | 'unconfigured' | 'error'>('loading');
  const [trustedContact, setTrustedContact] = useState<GetTrustedContactResponse['contact']>(null);

  useEffect(() => {
    if (!incident) return;
    let cancelled = false;
    setTrustedContactStatus('loading');
    getTrustedContact()
      .then((data) => {
        if (cancelled) return;
        if (data.configured && data.contact) {
          setTrustedContact(data.contact);
          setTrustedContactStatus('configured');
        } else {
          setTrustedContact(null);
          setTrustedContactStatus('unconfigured');
        }
      })
      .catch(() => {
        if (cancelled) return;
        setTrustedContact(null);
        setTrustedContactStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [incident?.incident_id]);

  const handleHelpRequest = useCallback(async () => {
    if (!incident || helpRequesting) return;
    setHelpRequesting(true);
    setHelpError(null);
    try {
      const result = await requestHelp(incident.incident_id);
      setHelpStory(result.help_story);
      setHelpDeliveryStatus(result.delivery_status);
      setHelpConfigured(result.trusted_contact_configured);
    } catch (err) {
      setHelpError(err instanceof Error ? err.message : 'Help request failed');
    } finally {
      setHelpRequesting(false);
    }
  }, [incident, helpRequesting]);

  const handleSubmitTranscript = useCallback(async () => {
    if (!transcriptText.trim()) return;
    setIsSubmitting(true);
    await submitTranscript(transcriptText.trim(), transcriptSource);
    setTranscriptText('');
    setIsSubmitting(false);
  }, [transcriptText, transcriptSource, submitTranscript]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedAudioFile(file);
    setUploadError(null);
    setUploadResult(null);
    setUploadedSegments([]);
  }, []);

  const handleUploadAudio = useCallback(async () => {
    if (!selectedAudioFile) return;
    const incidentId = (() => {
      try {
        return sessionStorage.getItem('lumina_current_incident_id');
      } catch {
        return null;
      }
    })();
    if (!incidentId) {
      setUploadError('No active incident. Start an incident first.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);
    setUploadedSegments([]);

    try {
      const credResult = await ensureDeviceIdentity();
      if (!credResult.ok) {
        setUploadError(`Device registration failed: ${credResult.error}`);
        setIsUploading(false);
        return;
      }

      const result = await uploadIncidentAudio(credResult.data, incidentId, selectedAudioFile);

      if (!result.ok) {
        setUploadError(`Upload failed: ${result.error}`);
        setIsUploading(false);
        return;
      }

      setUploadResult(result.data);

      // Present the transcribed segments from the backend response
      setUploadedSegments(result.data.segments ?? []);

      // Refresh incident state to show new timeline/evidence
      await refresh();
      setIsUploading(false);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Unexpected error');
      setIsUploading(false);
    }
  }, [selectedAudioFile, refresh]);

  const toggleProvenance = useCallback((key: string) => {
    setShowProvenance((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // ---- Loading / Error / Empty states ----

  if (status === 'loading') {
    return <LoadingState message="Loading incident…" />;
  }

  if (status === 'error' && error && !incident) {
    return (
      <ErrorState
        title="Could not load incident"
        message={error}
        status={errorCode ?? undefined}
        onRetry={refresh}
      />
    );
  }

  if (status === 'idle' || !incident) {
    return (
      <EmptyState
        title="No active incident"
        description="Start an incident to begin analyzing a suspicious interaction."
        action={
          <Button variant="primary" onClick={() => window.location.href = '/incident/new'}>
            Start Incident
          </Button>
        }
      />
    );
  }

  // ---- Extract data from incident ----

  const nextAction = incident.next_action;
  const observations = incident.timeline.filter(
    (e) => e.entry_type === 'EVIDENCE_ADDED' && e.metadata?.source === 'TRANSCRIPT',
  );
  const userActions = incident.user_actions;
  const exposureEntries = Object.entries(incident.exposure);
  const unknowns = incident.unknowns;
  const isClosed = incident.status === 'CLOSED';

  // Unconfirmed first-person action claims extracted from transcripts.
  // These are INFERENCE candidates only — they become real user actions only
  // after the user explicitly confirms below.
  const claimedActions = incident.timeline
    .filter(
      (e) =>
        e.entry_type === 'EVIDENCE_ADDED' &&
        e.metadata?.source === 'TRANSCRIPT_CLAIM',
    )
    .map((e) => ({
      actionType: String(e.metadata?.claimed_action_type ?? ''),
      description: String(e.metadata?.claimed_description ?? ''),
    }));

  // Escalation data from incident metadata (computed by escalation engine)
  const escalation = (incident.metadata?.escalation as EscalationResult | undefined) ?? null;

  // Conversation intelligence data (computed by intelligence layer)
  const intelligence = (incident.metadata?.conversation_intelligence as ConversationIntelligenceResult | undefined) ?? null;

  // ML intelligence data (computed by ML analysis layer)
  const mlIntel = (incident.metadata?.ml_intelligence as MLIntelligenceResult | undefined) ?? null;

  // Deterministic intervention decision (CP-29, computed by the safety engine)
  const intervention = (incident.metadata?.intervention as InterventionDecision | undefined) ?? null;
  const interventionLevel = intervention?.intervention_level ?? 'NONE';

  // Deterministic recovery snapshot (CP-30, computed by the safety engine).
  // AFTER_DAMAGE means at least one consequential action was confirmed; the
  // board is only shown then — before-damage incidents stay preventive.
  const recovery = (incident.metadata?.recovery as RecoverySnapshot | undefined) ?? null;
  const isRecoveryState = recovery?.phase === 'AFTER_DAMAGE';

  const heroActionTitle = isRecoveryState ? 'Next Recovery Action' : 'Next Safe Action';

  // ---- Immediately available extraction (pre-refresh) ----
  const extractionObservations = lastExtraction?.observations ?? [];

  // ---- Current situation: calm, plain-language, evidence-only ----
  const situationLead = (() => {
    switch (incident.status) {
      case 'ACTION_REQUIRED':
        return 'LUMINA has recorded something in this conversation worth pausing on.';
      case 'MONITORING':
        return 'LUMINA is watching this incident for new evidence.';
      case 'RECOVERING':
        return 'This incident is in recovery and LUMINA is tracking the steps taken so far.';
      case 'CLOSED':
        return 'This incident has been closed. What follows is the record for your files.';
      case 'UNKNOWN':
        return 'LUMINA could not confirm the current state of this incident.';
      default:
        return 'An incident is open and LUMINA is gathering evidence.';
    }
  })();

  const situationEvidence = Array.from(
    new Set(
      [
        ...observations.map((e) =>
          OBSERVATION_LABELS[String(e.metadata?.observation_type ?? '')] ??
          String(e.metadata?.observation_type ?? ''),
        ),
        ...extractionObservations.map(
          (o) => OBSERVATION_LABELS[o.observation_type] ?? o.observation_type,
        ),
      ].filter(Boolean),
    ),
  );

  // ---- Hero state (CP-28C): derived from real backend data ----

  const activeObservationTypes = (() => {
    const set = new Set<string>();
    observations.forEach((e) => {
      const t = String(e.metadata?.observation_type ?? '');
      if (t) set.add(t);
    });
    extractionObservations.forEach((o) => {
      if (o.observation_type) set.add(o.observation_type);
    });
    return set;
  })();

  const authorityPresent = [...activeObservationTypes].some((t) => AUTHORITY_OBSERVATION_TYPES.has(t));
  const pressurePresent = [...activeObservationTypes].some((t) => PRESSURE_OBSERVATION_TYPES.has(t));
  const requestPresent = [...activeObservationTypes].some((t) => REQUEST_OBSERVATION_TYPES.has(t));
  const escalationPresent = Boolean(
    escalation?.has_escalation ||
    intelligence?.dynamics.progression_direction === 'ESCALATING',
  );

  const heroState: HeroState = (() => {
    switch (incident.status) {
      case 'CLOSED':
        return 'CLOSED';
      case 'RECOVERING':
        return 'RECOVERING';
      case 'UNKNOWN':
        return 'UNKNOWN';
      case 'ACTION_REQUIRED':
        return 'ACTION_REQUIRED';
      default:
        break;
    }
    if (escalationPresent || authorityPresent || pressurePresent || requestPresent) {
      return 'PRESSURE';
    }
    if (observations.length > 0 || extractionObservations.length > 0) {
      return 'ATTENTION';
    }
    return 'CALM';
  })();

  const heroCopy = HERO_STATE_COPY[heroState];
  const heroChipClass = HERO_CHIP_CLASS[heroState];

  // ---- Pressure story (CP-28C): only the stages LUMINA recorded ----

  const pressureSteps = [
    {
      key: 'authority',
      present: authorityPresent,
      label: 'Authority claim',
      copy: 'Someone in the conversation claimed to hold authority or threatened legal consequences.',
    },
    {
      key: 'pressure',
      present: pressurePresent,
      label: 'Pressure',
      copy: 'Urgency or secrecy was used to press for a fast decision.',
    },
    {
      key: 'request',
      present: requestPresent,
      label: 'Request',
      copy: 'Something valuable was requested — money, credentials, personal information, or access.',
    },
  ].filter((s) => s.present);

  const hasPressureStory = pressureSteps.length > 0 || escalationPresent;

  // ---- Help: honest, real delivery state ----
  const helpStatusCopy: string | null = (() => {
    if (!helpDeliveryStatus) return null;
    if (helpConfigured === false || helpDeliveryStatus === 'NOT_CONFIGURED') {
      return 'A trusted contact is required for automatic delivery. The summary below can be shared manually.';
    }
    switch (helpDeliveryStatus) {
      case 'AUTHORIZED':
        return 'Your trusted contact has accepted this help request.';
      case 'QUEUED':
        return 'Help request queued for delivery...';
      case 'SENDING':
        return 'Sending your help request...';
      case 'SENT':
        return 'Help request sent to your trusted contact.';
      case 'DELIVERED':
        return 'Your trusted contact received your help request.';
      case 'FAILED':
        return 'Delivery failed. The summary below can be shared manually.';
      case 'UNKNOWN':
        return 'Help request recorded. Delivery status is unclear.';
      default:
        return 'Help request recorded.';
    }
  })();

  const helpStatusClass = (() => {
    if (helpConfigured === false || helpDeliveryStatus === 'NOT_CONFIGURED') {
      return 'incident-help-state--warn';
    }
    if (helpDeliveryStatus === 'DELIVERED' || helpDeliveryStatus === 'SENT' || helpDeliveryStatus === 'AUTHORIZED') {
      return 'incident-help-state--sent';
    }
    if (helpDeliveryStatus === 'FAILED') {
      return 'incident-help-state--error';
    }
    return 'incident-help-state--muted';
  })();

  // ---- Trusted human connection: delivery channel in plain words ----
  const trustedDeliveryLabel = (() => {
    switch (trustedContact?.delivery_channel) {
      case 'SMS':
        return 'Text message';
      case 'EMAIL':
        return 'Email';
      case 'NONE':
        return 'No delivery channel';
      default:
        return 'Message';
    }
  })();

  // ---- Audio state: honest human words ----
  const audioStateCopy = (() => {
    switch (streaming.state.status) {
      case 'IDLE':
        return { label: 'Ready', className: 'incident-chip--system' };
      case 'CAPTURING':
        return { label: 'Recording', className: 'incident-chip--warning' };
      case 'PROCESSING':
        return { label: 'Processing', className: 'incident-chip--warning' };
      case 'COMPLETE':
        return { label: 'Stopped', className: 'incident-chip--recovery' };
      case 'ERROR':
        return { label: 'Error', className: 'incident-chip--danger' };
      case 'ABORTED':
        return { label: 'Stopped', className: 'incident-chip--muted' };
      default:
        return { label: streaming.state.status, className: 'incident-chip--muted' };
    }
  })();

  const audioStatusMessage = (() => {
    switch (streaming.state.status) {
      case 'CAPTURING':
        return 'Recording microphone audio…';
      case 'PROCESSING':
        return 'Processing audio…';
      case 'COMPLETE':
        return 'Recording finished and analyzed.';
      case 'ERROR':
        return 'Recording could not be processed.';
      default:
        return null;
    }
  })();

  return (
    <div className="incident-view">
      {/* ---- 1. LIVE INCIDENT ---- */}
      <section
        className={`incident-masthead ${heroCopy.className}`}
        aria-labelledby="live-incident-title"
      >
        <span className="incident-eyebrow">Live incident</span>
        <div className="incident-masthead-headline-row">
          <h1
            id="live-incident-title"
            role="status"
            aria-label={`Incident status: ${INCIDENT_STATUS_LABELS[incident.status]}`}
            className={`incident-masthead-headline ${STATUS_CLASS[incident.status]}`}
          >
            {INCIDENT_STATUS_LABELS[incident.status]}
          </h1>
          {heroChipClass && heroCopy.chip && (
            <span
              aria-hidden="true"
              className={`incident-hero-chip ${heroChipClass}`}
            >
              {heroCopy.chip}
            </span>
          )}
        </div>
        <p className="incident-hero-lead">{heroCopy.lead}</p>
        <div className="incident-masthead-meta">
          <span>Priority: {INCIDENT_PRIORITY_LABELS[incident.priority]}</span>
          <span aria-hidden="true">·</span>
          <span>Started {formatDateTime(incident.created_at)}</span>
          {incident.updated_at && (
            <>
              <span aria-hidden="true">·</span>
              <span>Updated {formatDateTime(incident.updated_at)}</span>
            </>
          )}
        </div>
        <div className="incident-masthead-actions">
          <Button variant="ghost" size="sm" onClick={refresh}>
            Refresh
          </Button>
          {!isClosed && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void endIncident()}
              disabled={closing}
            >
              {closing ? 'Closing…' : 'End'}
            </Button>
          )}
        </div>

        {closeError && (
          <div role="alert" className="incident-banner incident-banner--error">
            {closeError}
          </div>
        )}

        {isClosed && (
          <p role="status" className="incident-banner incident-banner--closed">
            This incident is closed and archived. It remains readable for your
            records, and no further evidence is being collected.
          </p>
        )}
      </section>

      {/* ---- 2. CURRENT SITUATION ---- */}
      <IncidentSection
        id="current-situation"
        eyebrow="What's happening"
        title="Current Situation"
        subtitle="Plain-language reading of what LUMINA has recorded so far."
      >
        <div className="incident-situation">
          <p>{situationLead}</p>
          {situationEvidence.length > 0 && (
            <p className="incident-situation-evidence">
              In the conversation you shared, LUMINA recorded: {situationEvidence.join('; ')}.
            </p>
          )}
          {unknowns.length > 0 && (
            <p className="incident-situation-unknowns">
              Still unclear: {unknowns.join('; ')}.
            </p>
          )}
        </div>
        <p className="incident-note">
          This summarises evidence LUMINA has already recorded. It is not a
          judgment of anyone&rsquo;s intentions.
        </p>
      </IncidentSection>

      {/* ---- 3. NEXT SAFE ACTION (hero) ---- */}
      {nextAction ? (
        <section
          id="next-action"
          className={`incident-action-hero ${ACTION_CLASS[nextAction.urgency]}`}
          aria-labelledby="next-action-title"
        >
          <span className="incident-eyebrow">What you should do</span>
          <h2 id="next-action-title" className="incident-h2">{heroActionTitle}</h2>
          <p className="incident-action-text">{nextAction.action}</p>
          <p className="incident-action-reason">
            <strong>Why this matters:</strong> {nextAction.reason}
          </p>
          {Array.isArray(nextAction.evidence_basis) && nextAction.evidence_basis.length > 0 && (
            <p className="incident-action-reason" style={{ marginTop: 'var(--space-1)' }}>
              Based on: {nextAction.evidence_basis.join('; ')}.
            </p>
          )}
          {nextAction.official_channel_guidance && (
            <div className="incident-callout">{nextAction.official_channel_guidance}</div>
          )}
        </section>
      ) : heroState === 'CALM' ? (
        <section
          id="next-action"
          className="incident-action-hero incident-action-hero--none"
          aria-labelledby="next-action-title"
        >
          <span className="incident-eyebrow">What you should do</span>
          <h2 id="next-action-title" className="incident-h2">{heroActionTitle}</h2>
          <p className="incident-action-text">Pause. You don't have to decide right now.</p>
          <p className="incident-action-reason">
            <strong>Why this matters:</strong> nothing LUMINA has recorded needs
            immediate action. Staying calm and taking your time is a safe step by
            itself.
          </p>
        </section>
      ) : (
        <section
          id="next-action"
          className="incident-action-hero incident-action-hero--none"
          aria-labelledby="next-action-title"
        >
          <span className="incident-eyebrow">What you should do</span>
          <h2 id="next-action-title" className="incident-h2">{heroActionTitle}</h2>
          <p className="incident-action-text">
            LUMINA hasn't produced a recommended next action yet.
          </p>
          <p className="incident-action-reason">
            <strong>Why this matters:</strong> add evidence below, or press GET
            HELP if you are not safe.
          </p>
        </section>
      )}

      {/* ---- 3.5 LUMINA GUIDANCE (CP-29 deterministic intervention) ---- */}
      {intervention && interventionLevel !== 'NONE' && (
        <section
          id="intervention"
          className={`incident-section incident-intervention ${INTERVENTION_CLASS[interventionLevel] ?? ''}`}
          aria-labelledby="intervention-title"
        >
          <span className="incident-eyebrow">Guidance</span>
          <h2 id="intervention-title" className="incident-h2">LUMINA Guidance</h2>
          <p className="incident-intervention-lead">
            {INTERVENTION_LEAD_COPY[interventionLevel] ?? 'Take a moment before you continue.'}
          </p>
          {intervention.reason && (
            <p className="incident-intervention-reason">
              <strong>{INTERVENTION_WHY_LABEL[interventionLevel] ?? 'Why LUMINA is saying this:'}</strong>{' '}
              {intervention.reason}
            </p>
          )}
          <ul className="incident-intervention-actions">
            <li><a href="#next-action">See your next safe step</a></li>
            <li><a href="#conversation">Review the conversation</a></li>
            {(intervention.trusted_help_recommended || interventionLevel === 'HELP') && (
              <li><a href="#trusted-human">Connect with your trusted human</a></li>
            )}
            {interventionLevel === 'HELP' && (
              <li><a href="#incident-trapped">Ask for help now</a></li>
            )}
          </ul>
        </section>
      )}

      {/* ---- 3.6 RECOVERY & CONTINUITY (CP-30) ---- */}
      {recovery && isRecoveryState && (
        <IncidentSection
          id="recovery"
          eyebrow="Recovery"
          title="Recovery & Continuity"
          subtitle="A step in this incident was confirmed. Everything here comes from what you confirmed and the incident record."
        >
          <RecoveryBoard recovery={recovery} isClosed={isClosed} />
        </IncidentSection>
      )}

      {/* ---- 4. CONVERSATION (persisted record) ---- */}
      <IncidentSection
        id="conversation"
        eyebrow="Live record"
        title="Conversation"
        subtitle="Everything below comes from what has actually been recorded in this incident. LUMINA only sees what you add yourself."
      >
        {incident.timeline.length > 0 ? (
          <div className="incident-conversation">
            {incident.timeline.map((entry) => (
              <ConversationItem key={entry.entry_id} entry={entry} />
            ))}
          </div>
        ) : (
          <p className="incident-conv-summary">No events recorded yet.</p>
        )}
        <p className="incident-note">
          LUMINA does not record your phone calls. This record reflects only the
          transcripts and recordings you chose to add.
        </p>
      </IncidentSection>

      {/* ---- 5. PRESSURE STORY (evidence-grounded progression) ---- */}
      {hasPressureStory && (
        <IncidentSection
          id="pressure-story"
          eyebrow="Pattern"
          title="How the Pressure Built"
          subtitle="A step-by-step reading of the signals LUMINA recorded, in the order they typically appear. Only the stages it actually recorded are shown."
        >
          <p className="incident-pressure-headline">
            {escalationPresent
              ? 'LUMINA identified a pattern of increasing pressure.'
              : 'LUMINA noticed signals worth reviewing.'}
          </p>
          <ol className="incident-pressure-steps">
            {pressureSteps.map((step) => (
              <li key={step.key} className={`incident-pressure-step incident-pressure-step--${step.key}`}>
                <span aria-hidden="true" className="incident-pressure-node" />
                <div>
                  <div className="incident-pressure-label">{step.label}</div>
                  <p className="incident-pressure-copy">{step.copy}</p>
                </div>
              </li>
            ))}
            {escalationPresent && (
              <li className="incident-pressure-step incident-pressure-step--escalation">
                <span aria-hidden="true" className="incident-pressure-node" />
                <div>
                  <div className="incident-pressure-label">Escalation</div>
                  <p className="incident-pressure-copy">
                    The pressure increased over time as the conversation continued.
                  </p>
                </div>
              </li>
            )}
          </ol>
          <p className="incident-note">
            These are patterns in what was recorded — they are not proof of who
            is on the other side of the conversation.
          </p>
        </IncidentSection>
      )}

      {/* ---- 6. I'M TRAPPED — GET HELP ---- */}
      {!isClosed && (
        <section className="incident-trapped" id="incident-trapped" aria-labelledby="trapped-title">
          <div className="incident-trapped-header">
            <div>
              <span className="incident-eyebrow">Get help</span>
              <h2 id="trapped-title" className="incident-trapped-label">
                Need immediate help?
              </h2>
              <p className="incident-trapped-note">
                Press this at any time. It works on its own — separately from the
                microphone, speech recognition, and analysis. LUMINA writes a
                summary of this incident and sends it to your trusted contact.
              </p>
            </div>
            <button
              type="button"
              className="incident-trapped-button"
              onClick={handleHelpRequest}
              disabled={helpRequesting}
            >
              {helpRequesting ? 'Sending…' : "I'M TRAPPED — GET HELP"}
            </button>
          </div>

          {helpError && (
            <div role="alert" className="incident-help-state incident-help-state--error">
              {helpError}
            </div>
          )}

          {helpStatusCopy && !helpError && (
            <div role="status" aria-live="polite" className={`incident-help-state ${helpStatusClass}`}>
              {helpStatusCopy}
            </div>
          )}

          {helpStory && (
            <div className="incident-help-story">
              <div className="incident-eyebrow">
                Help summary for your trusted contact
              </div>
              <div className="incident-help-summary">{helpStory.one_line_summary}</div>
              {helpStory.sections.map((section, i) => (
                <div key={i}>
                  <div className="incident-conv-type">{section.heading}</div>
                  <div className="incident-note" style={{ marginTop: 0, whiteSpace: 'pre-line' }}>
                    {section.content}
                  </div>
                </div>
              ))}
              <div className="incident-note">{helpStory.privacy_note}</div>
            </div>
          )}
        </section>
      )}

      {/* ---- 7. TRUSTED HUMAN CONNECTION ---- */}
      {!isClosed && (
        <IncidentSection
          id="trusted-human"
          eyebrow="A real person"
          title="You don't have to handle this alone."
          subtitle="Help reaches you through a real person you chose — carried by your request, never by the analysis."
        >
          {trustedContactStatus === 'loading' && (
            <p className="incident-conv-summary">Checking your trusted contact…</p>
          )}
          {trustedContactStatus === 'error' && (
            <p className="incident-conv-summary">
              LUMINA couldn't confirm your trusted contact right now.
            </p>
          )}
          {trustedContactStatus === 'unconfigured' && (
            <div className="incident-stack">
              <p className="incident-conv-summary">No trusted contact is configured yet.</p>
              <p className="incident-note" style={{ marginTop: 0 }}>
                A trusted contact is a person you choose to receive LUMINA's help
                summaries. Nothing is sent until you ask.
              </p>
              <div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => { window.location.href = '/onboarding'; }}
                >
                  Set up a trusted contact
                </Button>
              </div>
            </div>
          )}
          {trustedContactStatus === 'configured' && trustedContact && (
            <div className="incident-trusted-card">
              <div className="incident-trusted-name">{trustedContact.display_name}</div>
              <div className="incident-trusted-detail">
                {trustedDeliveryLabel}
                {trustedContact.destination_masked && <> · {trustedContact.destination_masked}</>}
                {trustedContact.automatic_help_enabled && ' · automatic help is on'}
              </div>
              <p className="incident-trusted-status">
                {trustedContact.automatic_help_enabled
                  ? 'LUMINA can reach out to this contact when you press GET HELP.'
                  : 'LUMINA will only reach this contact when you press GET HELP.'}
              </p>
            </div>
          )}
        </IncidentSection>
      )}

      {/* ---- 8. WHAT MAY BE AT RISK ---- */}
      {exposureEntries.length > 0 && (
        <IncidentSection
          id="at-risk"
          eyebrow="What may be at risk"
          title="What May Be at Risk"
          subtitle="Based only on what LUMINA has recorded — it is not a guarantee."
        >
          <div className="incident-stack">
            {exposureEntries.map(([cat, state]) => (
              <div key={cat} className="incident-risk-row">
                <span className="incident-risk-label">
                  {EXPOSURE_CATEGORY_LABELS[cat as ExposureCategory]}
                </span>
                <span
                  role="status"
                  aria-label={`${EXPOSURE_CATEGORY_LABELS[cat as ExposureCategory]}: ${EXPOSURE_LEVEL_LABELS[state.level]}`}
                  className={`incident-risk-level ${RISK_LEVEL_CLASS[state.level]}`}
                >
                  {EXPOSURE_LEVEL_LABELS[state.level]}
                </span>
              </div>
            ))}
          </div>
        </IncidentSection>
      )}

      {/* ---- 9. WHAT WE KNOW ---- */}
      <IncidentSection
        id="what-we-know"
        eyebrow="What we know"
        title="What LUMINA Identified"
        subtitle="Evidence extracted from your transcripts"
      >
        {observations.length === 0 && extractionObservations.length === 0 ? (
          <p className="incident-conv-summary">
            No evidence has been extracted yet. Add a transcript below.
          </p>
        ) : (
          <div className="incident-stack">
            {/* From incident timeline */}
            {observations.map((entry) => {
              const obsType = String(entry.metadata?.observation_type ?? '');
              const label = OBSERVATION_LABELS[obsType] ?? obsType;
              const key = entry.entry_id;
              const isExpanded = showProvenance[key] ?? false;
              const textSpan = String(entry.metadata?.text_span ?? '');

              return (
                <div key={key}>
                  <button
                    type="button"
                    className="incident-known-item"
                    onClick={() => toggleProvenance(key)}
                    aria-expanded={isExpanded}
                    aria-controls={`provenance-${key}`}
                  >
                    <span aria-hidden="true" className="incident-known-dot" />
                    <span style={{ flex: 1 }}>{label}</span>
                    <span
                      aria-hidden="true"
                      className={`incident-known-chevron${isExpanded ? ' incident-known-chevron--open' : ''}`}
                    >
                      ▸
                    </span>
                  </button>
                  {isExpanded && textSpan && (
                    <div
                      id={`provenance-${key}`}
                      className="incident-known-detail"
                    >
                      <div>
                        <strong>Source:</strong> Transcript
                      </div>
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        <strong>Evidence:</strong> <em>&ldquo;{textSpan}&rdquo;</em>
                      </div>
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        <strong>Why:</strong>{' '}
                        {String(entry.metadata?.epistemic_note ?? 'Transcript evidence')}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* From immediate extraction (before refresh) */}
            {extractionObservations.map((obs) => {
              const label = OBSERVATION_LABELS[obs.observation_type] ?? obs.observation_type;
              const key = `ext-${obs.observation_type}`;
              const isExpanded = showProvenance[key] ?? false;

              return (
                <div key={key}>
                  <button
                    type="button"
                    className="incident-known-item"
                    onClick={() => toggleProvenance(key)}
                    aria-expanded={isExpanded}
                    aria-controls={`provenance-${key}`}
                  >
                    <span aria-hidden="true" className="incident-known-dot" />
                    <span style={{ flex: 1 }}>{label}</span>
                    <span
                      aria-hidden="true"
                      className={`incident-known-chevron${isExpanded ? ' incident-known-chevron--open' : ''}`}
                    >
                      ▸
                    </span>
                  </button>
                  {isExpanded && obs.text_span && (
                    <div
                      id={`provenance-${key}`}
                      className="incident-known-detail"
                    >
                      <div>
                        <strong>Source:</strong> Transcript
                      </div>
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        <strong>Evidence:</strong> <em>&ldquo;{obs.text_span}&rdquo;</em>
                      </div>
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        <strong>Why:</strong> {obs.epistemic_note}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </IncidentSection>

      {/* ---- 10. WHAT WE DON'T KNOW ---- */}
      {unknowns.length > 0 && (
        <IncidentSection
          id="what-we-dont-know"
          eyebrow="Open questions"
          title="What We Don't Know"
          subtitle="Information that requires your input or additional evidence"
        >
          <div className="incident-stack">
            {unknowns.map((u, i) => (
              <div key={i} className="incident-unknown-item">
                <span aria-hidden="true" className="incident-unknown-mark">
                  ?
                </span>
                {u}
              </div>
            ))}
          </div>
        </IncidentSection>
      )}

      {/* ---- 11. WHAT YOU CONFIRMED ---- */}
      {userActions.length > 0 && (
        <IncidentSection
          id="what-you-confirmed"
          eyebrow="Your record"
          title="What You Confirmed"
          subtitle="Actions you explicitly confirmed — LUMINA never assumes these happened."
        >
          <div className="incident-stack">
            {userActions.map((action) => (
              <div key={action.action_id} className="incident-confirmed-item">
                <span aria-hidden="true" className="incident-confirmed-mark">
                  ✓
                </span>
                <div>
                  <div className="incident-confirmed-label">
                    {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
                  </div>
                  <div className="incident-confirmed-note">You confirmed this happened.</div>
                </div>
              </div>
            ))}
          </div>
        </IncidentSection>
      )}

      {/* ---- 12. DID YOU ALREADY ACT? ---- */}
      {(observations.length > 0 || claimedActions.length > 0) && userActions.length === 0 && (
        <IncidentSection
          id="did-you-act"
          eyebrow="Your record"
          title="Did You Already Act?"
          subtitle="Only confirm if you actually performed the action"
        >
          {claimedActions.length > 0 && (
            <p className="incident-conv-summary">
              LUMINA noticed phrases in the transcript that suggest an action may have
              already happened. This is an unconfirmed signal — please confirm below
              only if you actually did it.
            </p>
          )}
          {claimedActions.length > 0 && (
            <div className="incident-stack" style={{ marginTop: 'var(--space-4)' }}>
              {claimedActions.map((claim, i) => (
                <Button
                  key={`${claim.actionType}-${i}`}
                  variant="danger"
                  size="sm"
                  onClick={() =>
                    confirmAction(claim.actionType, `User confirmed: ${claim.description}`)
                  }
                >
                  {ACTION_TYPE_LABELS[claim.actionType] ?? `Yes, ${claim.description}`}
                </Button>
              ))}
            </div>
          )}
          <p className="incident-conv-summary">
            Did you already share any requested information or take any requested action?
          </p>
          <div className="incident-grid-list" style={{ marginTop: 'var(--space-3)' }}>
            <Button
              variant="danger"
              size="sm"
              onClick={() => confirmAction('UNKNOWN_ACTION', 'User confirmed they acted but details unclear')}
            >
              Yes, I did something
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => confirmAction('DECLINED_REQUEST', 'User confirmed they did not act')}
            >
              No, I did not
            </Button>
          </div>
        </IncidentSection>
      )}

      {/* ---- 13. ANALYZE CONVERSATION ---- */}
      <IncidentSection
        id="analyze-conversation"
        eyebrow="Add a recording"
        title="Analyze Conversation"
        subtitle="Upload a recording you legitimately made, or record from your microphone. LUMINA will transcribe it and look for interaction patterns."
      >
        <div className="incident-stack">
          <p className="incident-conv-summary">
            LUMINA never records your calls without asking, and it does not listen
            to phone call audio — it only ever uses the microphone you start here,
            or audio files you choose to upload (WAV, MP3, FLAC, OGG, M4A, WebM).
            Anything you add is transcribed and analyzed.
          </p>

          <div className="incident-grid-list" style={{ alignItems: 'center' }}>
            <span className={`incident-chip ${audioStateCopy.className}`}>
              Audio: {audioStateCopy.label}
            </span>
            {!streaming.state.isRecording && streaming.state.status !== 'PROCESSING' && streaming.state.status !== 'COMPLETE' && (
              <Button
                variant="secondary"
                size="sm"
                onClick={streaming.startRecording}
              >
                Record Microphone
              </Button>
            )}
          </div>

          <div>
            <label htmlFor="audio-file-input" className="incident-field">
              Or choose a recording file
            </label>
            <input
              id="audio-file-input"
              type="file"
              accept=".wav,.mp3,.flac,.ogg,.m4a,.webm,audio/wav,audio/mpeg,audio/flac,audio/ogg,audio/mp4,audio/webm"
              onChange={handleFileChange}
              className="incident-input"
            />
          </div>

          {selectedAudioFile && (
            <div className="incident-risk-row" style={{ justifyContent: 'space-between' }}>
              <span className="incident-risk-label">{selectedAudioFile.name}</span>
              <Button
                variant="primary"
                size="sm"
                onClick={handleUploadAudio}
                disabled={isUploading}
              >
                {isUploading ? 'Analyzing conversation…' : 'Analyze Conversation'}
              </Button>
            </div>
          )}

          {uploadError && (
            <div role="alert" className="incident-help-state incident-help-state--error">
              {uploadError}
            </div>
          )}

          {/* Streaming session status */}
          {(streaming.state.isRecording || streaming.state.status === 'PROCESSING' || streaming.state.status === 'COMPLETE' || streaming.state.status === 'ERROR') && (
            <div className="incident-help-story" style={{ marginTop: 0, padding: 'var(--space-3)' }}>
              <div className="incident-risk-row" style={{ background: 'none', border: 'none', padding: 0 }}>
                <span className="incident-risk-label">
                  {audioStatusMessage ?? 'Audio session'}
                </span>
                {streaming.state.isRecording && (
                  <Button variant="secondary" size="sm" onClick={streaming.stopRecording}>
                    Stop &amp; Analyze
                  </Button>
                )}
                {(streaming.state.isRecording || streaming.state.status === 'PROCESSING') && (
                  <Button variant="secondary" size="sm" onClick={streaming.abortRecording}>
                    Cancel
                  </Button>
                )}
              </div>
              {streaming.state.status === 'CAPTURING' && (
                <div className="incident-conv-meta">
                  <span>Chunks: {streaming.state.totalChunks}</span>
                  <span>Segments: {streaming.state.totalSegments}</span>
                  <span>Observations: {streaming.state.totalObservations}</span>
                </div>
              )}
              {streaming.state.status === 'COMPLETE' && (
                <div className="incident-field-hint" style={{ color: 'var(--lumina-system)' }}>
                  {streaming.state.totalSegments} transcript segment(s) produced from {streaming.state.totalChunks} chunk(s).
                  {streaming.state.totalObservations > 0 && (
                    <> {streaming.state.totalObservations} observation(s) identified.</>
                  )}
                </div>
              )}
              {streaming.state.error && (
                <div role="alert" className="incident-help-state incident-help-state--error">
                  {streaming.state.error}
                </div>
              )}
            </div>
          )}

          {uploadResult && !uploadError && (
            <div className="incident-stack">
              <div role="status" className="incident-field-hint" style={{ color: 'var(--lumina-system)', marginTop: 0 }}>
                Conversation analyzed. Transcript and observations added to incident.
              </div>
              {uploadResult.transcription && (
                <div className="incident-note" style={{ fontFamily: 'var(--font-mono)' }}>
                  model: {uploadResult.transcription.model} · device: {uploadResult.transcription.device} · lang: {uploadResult.transcription.language}
                  {typeof uploadResult.transcription.duration_seconds === 'number' && (
                    <> · audio: {uploadResult.transcription.duration_seconds.toFixed(1)}s</>
                  )}
                </div>
              )}

              {/* Timestamped transcribed segments */}
              {uploadedSegments.length > 0 && (
                <div className="incident-seg-list">
                  <div className="incident-eyebrow">What LUMINA heard</div>
                  {uploadedSegments.map((seg) => (
                    <div key={seg.segment_id} className="incident-known-detail" style={{ margin: 0 }}>
                      <div className="incident-conv-meta">
                        {(seg.start_time !== undefined || seg.end_time !== undefined) && (
                          <span className="incident-conv-time">
                            {seg.start_time !== undefined ? `${seg.start_time.toFixed(1)}s` : ''}
                            {seg.start_time !== undefined && seg.end_time !== undefined ? ' – ' : ''}
                            {seg.end_time !== undefined ? `${seg.end_time.toFixed(1)}s` : ''}
                          </span>
                        )}
                        {seg.speaker === 'CALLER' && (
                          <span className="incident-conv-badge incident-conv-badge--caller">Caller</span>
                        )}
                        {seg.speaker === 'USER' && (
                          <span className="incident-conv-badge incident-conv-badge--user">You</span>
                        )}
                        {seg.speaker === 'UNKNOWN' && seg.speaker_attribution_method && (
                          <span className="incident-conv-time">Not sure who the speaker was</span>
                        )}
                      </div>
                      <div className="incident-conv-summary" style={{ marginTop: 0 }}>
                        {seg.text}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted observations */}
              {uploadResult.observations_extracted > 0 && (
                <div className="incident-field-hint" style={{ color: 'var(--lumina-warning)', marginTop: 0 }}>
                  {uploadResult.observations_extracted} observation(s) identified from this conversation.
                  {escalation && escalation.has_escalation && (
                    <> Escalation patterns are shown in Technical Analysis below.</>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </IncidentSection>

      {/* ---- 14. ADD MORE EVIDENCE ---- */}
      <IncidentSection
        id="add-evidence"
        eyebrow="Add a transcript"
        title="Add More Evidence"
        subtitle="Paste or type what was said"
      >
        <div className="incident-stack">
          <div>
            <label htmlFor="transcript-source" className="incident-field">
              Source
            </label>
            <select
              id="transcript-source"
              className="incident-select"
              value={transcriptSource}
              onChange={(e) => setTranscriptSource(e.target.value as TranscriptSource)}
            >
              <option value="USER_TYPED">User typed</option>
              <option value="USER_DICTATED">User dictated</option>
              <option value="MESSAGE_FORWARD">Message forwarded</option>
              <option value="STT_PROVIDER" disabled>
                Speech-to-text (add via audio upload below)
              </option>
            </select>
            <div className="incident-field-hint">
              Local transcription runs on your device. Transcribed segments report
              speaker as unknown — LUMINA does not attempt speaker identification.
            </div>
          </div>

          <div>
            <label htmlFor="transcript-text" className="incident-field">
              Transcript
            </label>
            <textarea
              id="transcript-text"
              className="incident-textarea"
              value={transcriptText}
              onChange={(e) => setTranscriptText(e.target.value)}
              placeholder="Paste or type what was said..."
              rows={5}
            />
          </div>

          <Button
            variant="primary"
            onClick={handleSubmitTranscript}
            disabled={!transcriptText.trim() || isSubmitting || isClosed}
          >
            {isSubmitting ? 'Submitting…' : 'Submit Transcript'}
          </Button>

          {isClosed && (
            <p className="incident-conv-summary">
              This incident is closed. Start a new incident to add more evidence.
            </p>
          )}
        </div>
      </IncidentSection>

      {/* ---- 15. TECHNICAL ANALYSIS (progressive disclosure) ---- */}
      <details className="incident-details">
        <summary>
          <span>Technical Analysis</span>
          <span aria-hidden="true" className="incident-known-chevron">▸</span>
        </summary>
        <div className="incident-details-body">
          <p className="incident-note" style={{ marginTop: 0 }}>
            These analyses describe patterns LUMINA&rsquo;s models observed in the
            evidence. They are not a verdict and do not attribute intent.
          </p>

          {/* ---- Conversation escalations (CP-13) ---- */}
          {escalation && escalation.has_escalation && (
            <section aria-labelledby="ta-escalation-title">
              <h3 id="ta-escalation-title" className="incident-h3">Conversation Escalation</h3>
              <p className="incident-note" style={{ marginTop: 0 }}>
                Pattern analysis only — this is not proof of fraud. LUMINA identifies
                interaction patterns from available evidence; it does not determine intent.
              </p>
              <div className="incident-stack" style={{ marginTop: 'var(--space-3)' }}>
                {escalation.patterns.map((pattern) => (
                  <div key={pattern.pattern_id}>
                    <div className="incident-conv-type-row" style={{ flexWrap: 'wrap' }}>
                      <span className="incident-conv-type">{pattern.pattern_name}</span>
                      <span className={`incident-chip incident-chip--trial ${STAGE_CHIP_CLASS[pattern.stage] ?? 'incident-chip--muted'}`}>
                        {ESCALATION_STAGE_LABELS[pattern.stage] ?? pattern.stage}
                      </span>
                      {pattern.status === 'COMPLETE' && (
                        <span className="incident-chip incident-chip--trial incident-chip--danger">Complete</span>
                      )}
                    </div>
                    <div className="incident-stack" style={{ gap: 0, marginTop: 'var(--space-2)' }}>
                      {pattern.stages_matched.map((stage, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '16px' }}>
                            <div
                              style={{
                                width: '8px', height: '8px', borderRadius: '50%',
                                background: STAGE_CHIP_CLASS[ pattern.stage ] === 'incident-chip--danger'
                                  ? 'var(--lumina-danger)'
                                  : STAGE_CHIP_CLASS[ pattern.stage ] === 'incident-chip--warning'
                                    ? 'var(--lumina-warning)'
                                    : 'var(--lumina-system)',
                                flexShrink: 0, marginTop: '5px',
                              }}
                            />
                            {i < pattern.stages_matched.length - 1 && (
                              <div style={{ width: '1px', height: '16px', background: 'var(--lumina-border-subtle)' }} />
                            )}
                          </div>
                          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-normal)' }}>
                            {OBSERVATION_LABELS[stage] ?? stage}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="incident-note" style={{ marginTop: 'var(--space-2)' }}>
                      {pattern.explanation}
                    </p>
                  </div>
                ))}
                {escalation.repeated_requests.length > 0 && (
                  <div className="incident-help-story" style={{ padding: 'var(--space-3)' }}>
                    <div className="incident-eyebrow">Repeated Requests</div>
                    {escalation.repeated_requests.map((r) => (
                      <div key={r.request_type} className="incident-conv-summary">
                        {r.explanation}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ---- Conversation intelligence (CP-20) ---- */}
          {intelligence && intelligence.events.length > 0 && (
            <section aria-labelledby="ta-dynamics-title">
              <h3 id="ta-dynamics-title" className="incident-h3">Conversation Dynamics</h3>
              <p className="incident-note" style={{ marginTop: 0 }}>
                Behavioral pattern analysis from available evidence — this is not
                proof of fraud and does not determine intent.
              </p>

              {/* Progression direction */}
              <div style={{ marginTop: 'var(--space-3)' }}>
                <span className="incident-eyebrow">Progression</span>
                <div className="incident-grid-list" style={{ marginTop: 'var(--space-1)' }}>
                  <span
                    className={`incident-chip ${intelligence.dynamics.progression_direction === 'ESCALATING'
                      ? 'incident-chip--warning'
                      : 'incident-chip--recovery'}`}
                  >
                    {intelligence.dynamics.progression_direction.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>

              {/* Behavioral categories present */}
              {intelligence.dynamics.categories_present.length > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <span className="incident-eyebrow">Detected Behaviors</span>
                  <div className="incident-grid-list" style={{ marginTop: 'var(--space-1)' }}>
                    {intelligence.dynamics.categories_present.map((cat) => (
                      <span key={cat} className="incident-chip incident-chip--muted">
                        {cat.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (l) => l.toUpperCase())}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Transitions */}
              {intelligence.dynamics.transitions.length > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <span className="incident-eyebrow">Behavioral Transitions</span>
                  <div className="incident-stack" style={{ marginTop: 'var(--space-1)' }}>
                    {intelligence.dynamics.transitions.map((t, i) => (
                      <div key={t.transition_id} className="incident-conv-summary">
                        <span style={{ color: 'var(--lumina-text-muted)' }}>{i + 1}.</span> {t.explanation}
                        {t.time_gap_seconds !== null && (
                          <span style={{ color: 'var(--lumina-text-muted)', fontSize: 'var(--text-xs)' }}>
                            {' '}– {Math.round(t.time_gap_seconds)}s gap
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Advisory interventions */}
              {intelligence.interventions.length > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <span className="incident-eyebrow">Suggested Interventions</span>
                  <div className="incident-stack" style={{ marginTop: 'var(--space-1)' }}>
                    {intelligence.interventions.map((intv, i) => (
                      <div key={i} className="incident-conv-summary">
                        <span className={`incident-chip incident-chip--trial ${intv.priority === 'HIGH' ? 'incident-chip--danger' : 'incident-chip--warning'}`}>
                          {intv.priority}
                        </span>
                        {' '}{intv.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Overall assessment */}
              <p className="incident-note" style={{ marginTop: 'var(--space-3)' }}>
                {intelligence.dynamics.overall_assessment}
              </p>

              {/* Model status */}
              {intelligence.model_metadata?.model_status === 'NOT_TRAINED' && (
                <p className="incident-note" style={{ marginTop: 'var(--space-2)' }}>
                  Analysis model: deterministic feature extraction (no model trained on this deployment).
                </p>
              )}
            </section>
          )}

          {/* ---- ML tactic analysis (CP-22) ---- */}
          {mlIntel && mlIntel.tactic_predictions.length > 0 && (
            <section aria-labelledby="ta-ml-title">
              <h3 id="ta-ml-title" className="incident-h3">ML Tactic Analysis</h3>
              <p className="incident-note" style={{ marginTop: 0 }}>
                Descriptions of patterns observed in evidence — not proof of fraud.
              </p>

              {/* Model status */}
              {mlIntel.model_metadata?.model_status === 'NOT_TRAINED' && (
                <p className="incident-note" style={{ marginTop: 'var(--space-3)', fontFamily: 'var(--font-mono)' }}>
                  model_status: NOT_TRAINED — deterministic baseline in use (no suitable dataset identified during implementation).
                </p>
              )}

              {/* Phase prediction */}
              {mlIntel.phase_prediction && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <span className="incident-eyebrow">Conversation Phase</span>
                  <div className="incident-grid-list" style={{ marginTop: 'var(--space-1)' }}>
                    <span
                      className={`incident-chip ${
                        mlIntel.phase_prediction.phase === 'EXTRACTION' || mlIntel.phase_prediction.phase === 'ESCALATION'
                          ? 'incident-chip--warning'
                          : 'incident-chip--muted'
                      }`}
                    >
                      {mlIntel.phase_prediction.phase}
                    </span>
                  </div>
                </div>
              )}

              {/* Observed tactics */}
              {mlIntel.observed_tactics.length > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <span className="incident-eyebrow">Detected Tactics</span>
                  <div className="incident-grid-list" style={{ marginTop: 'var(--space-1)' }}>
                    {mlIntel.observed_tactics.map((tactic) => (
                      <span key={tactic} className="incident-chip incident-chip--muted">
                        {tactic.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (l) => l.toUpperCase())}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Explanation */}
              <p className="incident-note" style={{ marginTop: 'var(--space-3)' }}>
                {mlIntel.explanation}
              </p>

              {/* Uncertainties */}
              {mlIntel.uncertainties.length > 0 && (
                <div style={{ marginTop: 'var(--space-2)' }}>
                  <span className="incident-eyebrow">Limitations</span>
                  <ul style={{ marginTop: 'var(--space-1)', paddingLeft: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', listStyle: 'disc' }}>
                    {mlIntel.uncertainties.map((u, i) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {!escalation?.has_escalation && !(intelligence && intelligence.events.length > 0) &&
            !(mlIntel && mlIntel.tactic_predictions.length > 0) && (
            <p className="incident-note" style={{ marginTop: 0 }}>
              No technical analysis has been produced for this incident yet. Add a
              transcript or recording and LUMINA will generate analysis here.
            </p>
          )}
        </div>
      </details>
    </div>
  );
}