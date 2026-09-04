/* ============================================================
   LUMINA Incident View Page
   ============================================================
   The core incident copilot experience.
   Shows: status, next action, evidence, exposure, timeline,
   transcript input, and user action confirmation.
   ============================================================ */

import { useState, useCallback } from 'react';
import { useIncidentState, INCIDENT_STATUS_LABELS, INCIDENT_PRIORITY_LABELS } from '@/hooks/useIncidentState';
import { useStreamingSession } from '@/hooks/useStreamingSession';
import { uploadIncidentAudio } from '@/lib/api/incidents';
import { requestHelp } from '@/lib/api/help';
import { ensureDeviceIdentity } from '@/lib/api/device';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';
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
  NOT_INDICATED: 'Not indicated',
  POTENTIALLY_EXPOSED: 'Potentially exposed',
  USER_CONFIRMED_EXPOSED: 'Confirmed exposed',
  UNKNOWN: 'Unknown',
};

const EXPOSURE_LEVEL_COLORS: Record<ExposureLevel, string> = {
  NOT_INDICATED: 'var(--lumina-text-muted)',
  POTENTIALLY_EXPOSED: 'var(--lumina-warning)',
  USER_CONFIRMED_EXPOSED: 'var(--lumina-danger)',
  UNKNOWN: 'var(--lumina-text-muted)',
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
};

const ESCALATION_STAGE_LABELS: Record<string, string> = {
  SETUP: 'Setup',
  PRESSURE: 'Pressure',
  EXTRACTION: 'Extraction',
};

const ESCALATION_STAGE_COLORS: Record<string, string> = {
  SETUP: 'var(--lumina-system)',
  PRESSURE: 'var(--lumina-warning)',
  EXTRACTION: 'var(--lumina-danger)',
};

const STATUS_COLORS: Record<IncidentStatus, string> = {
  ACTIVE: 'var(--lumina-system)',
  MONITORING: 'var(--lumina-warning)',
  ACTION_REQUIRED: 'var(--lumina-danger)',
  RECOVERING: 'var(--lumina-investigation)',
  CLOSED: 'var(--lumina-recovery)',
  UNKNOWN: 'var(--lumina-text-muted)',
};

const PRIORITY_COLORS: Record<Priority, string> = {
  IMMEDIATE: 'var(--lumina-danger)',
  HIGH: 'var(--lumina-warning)',
  MEDIUM: 'var(--lumina-action)',
  LOW: 'var(--lumina-text-secondary)',
  NONE: 'var(--lumina-text-muted)',
};

// ---- Timeline formatting ----

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// ---- Main Component ----

export function IncidentViewPage() {
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
  } = useIncidentState();

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
  const [helpStory, setHelpStory] = useState<import('@/types/incident').HelpStory | null>(null);
  const [helpError, setHelpError] = useState<string | null>(null);
  const [helpDeliveryStatus, setHelpDeliveryStatus] = useState<string | null>(null);

  const handleHelpRequest = useCallback(async () => {
    if (!incident || helpRequesting) return;
    setHelpRequesting(true);
    setHelpError(null);
    try {
      const result = await requestHelp(incident.incident_id);
      setHelpStory(result.help_story);
      setHelpDeliveryStatus(result.delivery_status);
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

  // ---- Loading / Error states ----

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
  const exposureEntries = Object.entries(incident.exposure).filter(
    ([, v]) => v.level !== 'NOT_INDICATED',
  );
  const unknowns = incident.unknowns;

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


  // ---- Get observations from last extraction (immediate display) ----
  const extractionObservations = lastExtraction?.observations ?? [];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-6)',
        maxWidth: '48rem',
        margin: '0 auto',
      }}
    >
      {/* ---- INCIDENT STATUS ---- */}
      <Card
        elevated
        glow
        style={{
          borderLeft: `3px solid ${STATUS_COLORS[incident.status]}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div>
            <div
              role="status"
              aria-label={`Incident status: ${INCIDENT_STATUS_LABELS[incident.status]}`}
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: STATUS_COLORS[incident.status],
                marginBottom: 'var(--space-1)',
              }}
            >
              {INCIDENT_STATUS_LABELS[incident.status]}
            </div>
            <div
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-muted)',
              }}
            >
              Priority: {INCIDENT_PRIORITY_LABELS[incident.priority]}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button variant="ghost" size="sm" onClick={refresh}>
              Refresh
            </Button>
            {incident.status !== 'CLOSED' && (
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
        </div>

        {closeError && (
          <div
            role="alert"
            style={{
              marginTop: 'var(--space-3)',
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-danger)',
              lineHeight: 'var(--leading-relaxed)',
            }}
          >
            {closeError}
          </div>
        )}

        {incident.status === 'CLOSED' && (
          <div
            role="status"
            style={{
              marginTop: 'var(--space-3)',
              padding: 'var(--space-3)',
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
              background: 'rgba(0, 0, 0, 0.15)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border-subtle)',
            }}
          >
            This incident is closed and archived. It remains readable for your
            records, and no further evidence is being collected.
          </div>
        )}
      </Card>

      {/* ---- NEXT SAFEST ACTION (HERO) ---- */}
      {nextAction ? (
        <Card
          elevated
          glow
          style={{
            borderLeft: `3px solid ${PRIORITY_COLORS[nextAction.urgency]}`,
            background: 'var(--lumina-surface-elevated)',
          }}
        >
          <SectionHeader
            number={1}
            title="Next Safest Action"
            subtitle="The single most important thing to do right now"
          />
          <p
            role="alert"
            style={{
              fontSize: 'var(--text-lg)',
              fontWeight: 700,
              color: 'var(--lumina-text)',
              lineHeight: 'var(--leading-relaxed)',
              marginBottom: 'var(--space-3)',
            }}
          >
            {nextAction.action}
          </p>
          <p
            style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
              marginBottom: nextAction.official_channel_guidance ? 'var(--space-3)' : 0,
            }}
          >
            {nextAction.reason}
          </p>
          {nextAction.official_channel_guidance && (
            <div
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-system)',
                lineHeight: 'var(--leading-relaxed)',
                padding: 'var(--space-3)',
                background: 'var(--lumina-system-soft)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid rgba(94, 196, 212, 0.2)',
              }}
            >
              {nextAction.official_channel_guidance}
            </div>
          )}
        </Card>
      ) : (
        <Card>
          <EmptyState
            title="No immediate action identified"
            description="Add a transcript to help LUMINA understand the situation."
          />
        </Card>
      )}

      {/* ---- I'M TRAPPED — GET HELP ---- */}
      {incident && incident.status !== 'CLOSED' && (
        <Card elevated style={{ borderLeft: '3px solid var(--lumina-danger)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--lumina-danger)' }}>
                  Need immediate help?
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', marginTop: '2px' }}>
                  Press this at any time — LUMINA will generate a help story for your trusted contact.
                </div>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={handleHelpRequest}
                disabled={helpRequesting}
                style={{
                  background: 'var(--lumina-danger)',
                  color: 'white',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {helpRequesting ? 'Sending…' : "I'M TRAPPED — GET HELP"}
              </Button>
            </div>
            {helpError && (
              <div role="alert" style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-danger)' }}>
                {helpError}
              </div>
            )}
            {helpDeliveryStatus && !helpError && (
              <div style={{
                fontSize: 'var(--text-xs)',
                padding: 'var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                color: helpDeliveryStatus === 'SENT' || helpDeliveryStatus === 'DELIVERED'
                  ? 'var(--lumina-system)'
                  : helpDeliveryStatus === 'NOT_CONFIGURED'
                    ? 'var(--lumina-warning)'
                    : 'var(--lumina-text-muted)',
                background: 'rgba(0, 0, 0, 0.1)',
              }}>
                {helpDeliveryStatus === 'NOT_CONFIGURED' && 'Trusted contact not configured. Help story shown below — share it manually if needed.'}
                {helpDeliveryStatus === 'SENT' && 'Help request sent to trusted contact.'}
                {helpDeliveryStatus === 'DELIVERED' && 'Help request delivered to trusted contact.'}
                {helpDeliveryStatus === 'FAILED' && 'Help request delivery failed. Help story shown below.'}
                {helpDeliveryStatus === 'UNKNOWN' && 'Help request recorded. Delivery status uncertain.'}
                {helpDeliveryStatus === 'QUEUED' && 'Help request queued for delivery...'}
              </div>
            )}
            {helpStory && (
              <div style={{
                padding: 'var(--space-3)',
                background: 'rgba(0, 0, 0, 0.15)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--lumina-border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-2)',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-wider)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)' }}>
                  Help Story — {helpStory.urgency}
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text)', fontWeight: 600 }}>
                  {helpStory.one_line_summary}
                </div>
                {helpStory.sections.map((section, i) => (
                  <div key={i}>
                    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--lumina-text-secondary)', marginTop: 'var(--space-2)' }}>
                      {section.heading}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', lineHeight: 'var(--leading-relaxed)', whiteSpace: 'pre-line' }}>
                      {section.content}
                    </div>
                  </div>
                ))}
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', fontStyle: 'italic', marginTop: 'var(--space-2)' }}>
                  {helpStory.privacy_note}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ---- CONVERSATION ESCALATION ---- */}
      {escalation && escalation.has_escalation && (
        <Card elevated style={{ borderLeft: '3px solid var(--lumina-warning)' }}>
          <SectionHeader
            number={1.5}
            title="Conversation Escalation"
            subtitle="Pattern analysis only — this is not proof of fraud"
          />
          <p style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--lumina-text-muted)',
            lineHeight: 'var(--leading-relaxed)',
            marginBottom: 'var(--space-3)',
            fontStyle: 'italic',
          }}>
            LUMINA identifies interaction patterns from available evidence; it does not determine intent.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {escalation.patterns.map((pattern) => (
              <div key={pattern.pattern_id}>
                <div style={{
                  fontSize: 'var(--text-sm)',
                  fontWeight: 700,
                  color: 'var(--lumina-text)',
                  marginBottom: 'var(--space-2)',
                }}>
                  {pattern.pattern_name}
                  <span style={{
                    marginLeft: 'var(--space-2)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    color: ESCALATION_STAGE_COLORS[pattern.stage] ?? 'var(--lumina-text-muted)',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(0,0,0,0.15)',
                  }}>
                    {ESCALATION_STAGE_LABELS[pattern.stage] ?? pattern.stage}
                  </span>
                  {pattern.status === 'COMPLETE' && (
                    <span style={{
                      marginLeft: 'var(--space-2)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--lumina-danger)',
                    }}>
                      ●
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {pattern.stages_matched.map((stage, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '16px' }}>
                        <div style={{
                          width: '8px', height: '8px', borderRadius: '50%',
                          background: ESCALATION_STAGE_COLORS[
                            // Map observation type to its stage
                            ['AUTHORITY_CLAIM'].includes(stage) ? 'SETUP'
                            : ['THREAT_OF_ARREST', 'THREAT_OF_LEGAL_ACTION', 'URGENCY', 'SECRECY_REQUEST', 'INDEPENDENT_VERIFICATION_BLOCKED', 'CALL_BACK_INSTRUCTION'].includes(stage) ? 'PRESSURE'
                            : 'EXTRACTION'
                          ] ?? 'var(--lumina-text-muted)',
                          flexShrink: 0, marginTop: '5px',
                        }} />
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
                <p style={{
                  fontSize: 'var(--text-xs)',
                  color: 'var(--lumina-text-muted)',
                  lineHeight: 'var(--leading-relaxed)',
                  marginTop: 'var(--space-2)',
                  fontStyle: 'italic',
                }}>
                  {pattern.explanation}
                </p>
              </div>
            ))}
            {escalation.repeated_requests.length > 0 && (
              <div style={{
                padding: 'var(--space-3)',
                background: 'rgba(0,0,0,0.15)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--lumina-border-subtle)',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-wider)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)', marginBottom: 'var(--space-2)' }}>
                  Repeated Requests
                </div>
                {escalation.repeated_requests.map((r) => (
                  <div key={r.request_type} style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', marginBottom: '2px' }}>
                    {r.explanation}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ---- WHAT LUMINA KNOWS (Evidence) ---- */}
      <Card>
        <SectionHeader
          number={escalation && escalation.has_escalation ? 3 : 2}
          title="What LUMINA Identified"
          subtitle="Evidence extracted from your transcripts"
        />
        {observations.length === 0 && extractionObservations.length === 0 ? (
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-muted)' }}>
            No evidence has been extracted yet. Add a transcript below.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
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
                    onClick={() => toggleProvenance(key)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 'var(--space-3)',
                      width: '100%',
                      textAlign: 'left',
                      background: 'none',
                      border: 'none',
                      padding: 'var(--space-3)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      color: 'var(--lumina-text)',
                      fontSize: 'var(--text-sm)',
                      lineHeight: 'var(--leading-relaxed)',
                      transition: 'background var(--duration-fast) var(--ease-out)',
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.background = 'var(--lumina-surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background = 'none';
                    }}
                  >
                    <span
                      aria-hidden="true"
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: 'var(--lumina-investigation)',
                        flexShrink: 0,
                        marginTop: '0.4rem',
                      }}
                    />
                    <span style={{ flex: 1 }}>{label}</span>
                    <span
                      aria-hidden="true"
                      style={{
                        color: 'var(--lumina-text-muted)',
                        fontSize: 'var(--text-xs)',
                        transform: isExpanded ? 'rotate(90deg)' : 'none',
                        transition: 'transform var(--duration-fast) var(--ease-out)',
                      }}
                    >
                      ▸
                    </span>
                  </button>
                  {isExpanded && textSpan && (
                    <div
                      style={{
                        marginLeft: 'var(--space-6)',
                        padding: 'var(--space-3)',
                        background: 'rgba(0, 0, 0, 0.2)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--lumina-border-subtle)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--lumina-text-muted)',
                        lineHeight: 'var(--leading-relaxed)',
                      }}
                    >
                      <div style={{ marginBottom: 'var(--space-2)' }}>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Source:</strong>{' '}
                        Transcript
                      </div>
                      <div style={{ marginBottom: 'var(--space-2)' }}>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Evidence:</strong>{' '}
                        <em>"{textSpan}"</em>
                      </div>
                      <div>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Why:</strong>{' '}
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
                    onClick={() => toggleProvenance(key)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 'var(--space-3)',
                      width: '100%',
                      textAlign: 'left',
                      background: 'none',
                      border: 'none',
                      padding: 'var(--space-3)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      color: 'var(--lumina-text)',
                      fontSize: 'var(--text-sm)',
                      lineHeight: 'var(--leading-relaxed)',
                      transition: 'background var(--duration-fast) var(--ease-out)',
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.background = 'var(--lumina-surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background = 'none';
                    }}
                  >
                    <span
                      aria-hidden="true"
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: 'var(--lumina-investigation)',
                        flexShrink: 0,
                        marginTop: '0.4rem',
                      }}
                    />
                    <span style={{ flex: 1 }}>{label}</span>
                    <span
                      aria-hidden="true"
                      style={{
                        color: 'var(--lumina-text-muted)',
                        fontSize: 'var(--text-xs)',
                        transform: isExpanded ? 'rotate(90deg)' : 'none',
                        transition: 'transform var(--duration-fast) var(--ease-out)',
                      }}
                    >
                      ▸
                    </span>
                  </button>
                  {isExpanded && obs.text_span && (
                    <div
                      style={{
                        marginLeft: 'var(--space-6)',
                        padding: 'var(--space-3)',
                        background: 'rgba(0, 0, 0, 0.2)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--lumina-border-subtle)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--lumina-text-muted)',
                        lineHeight: 'var(--leading-relaxed)',
                      }}
                    >
                      <div style={{ marginBottom: 'var(--space-2)' }}>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Source:</strong>{' '}
                        Transcript
                      </div>
                      <div style={{ marginBottom: 'var(--space-2)' }}>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Evidence:</strong>{' '}
                        <em>"{obs.text_span}"</em>
                      </div>
                      <div>
                        <strong style={{ color: 'var(--lumina-text-secondary)' }}>Why:</strong>{' '}
                        {obs.epistemic_note}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* ---- EXPOSURE PANEL ---- */}
      {exposureEntries.length > 0 && (
        <Card>
          <SectionHeader
            number={3}
            title="What May Be at Risk"
            subtitle="Exposure assessment based on evidence"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {exposureEntries.map(([cat, state]) => (
              <div
                key={cat}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: 'var(--space-3)',
                  background: 'rgba(0, 0, 0, 0.15)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--lumina-border-subtle)',
                }}
              >
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text)' }}>
                  {EXPOSURE_CATEGORY_LABELS[cat as ExposureCategory]}
                </span>
                <span
                  role="status"
                  aria-label={`${EXPOSURE_CATEGORY_LABELS[cat as ExposureCategory]}: ${EXPOSURE_LEVEL_LABELS[state.level]}`}
                  style={{
                    fontSize: 'var(--text-xs)',
                    fontWeight: 700,
                    color: EXPOSURE_LEVEL_COLORS[state.level],
                    letterSpacing: 'var(--tracking-wide)',
                  }}
                >
                  {EXPOSURE_LEVEL_LABELS[state.level]}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ---- UNKNOWN INFORMATION ---- */}
      {unknowns.length > 0 && (
        <Card>
          <SectionHeader
            number={4}
            title="What We Don't Know"
            subtitle="Information that requires your input or additional evidence"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {unknowns.map((u, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-3)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--lumina-text-secondary)',
                  lineHeight: 'var(--leading-relaxed)',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    color: 'var(--lumina-text-muted)',
                    flexShrink: 0,
                    marginTop: '0.1rem',
                  }}
                >
                  ?
                </span>
                {u}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ---- USER ACTION CONFIRMATION ---- */}
      {(observations.length > 0 || claimedActions.length > 0) && userActions.length === 0 && (
        <Card>
          <SectionHeader
            number={5}
            title="Did You Already Act?"
            subtitle="Only confirm if you actually performed the action"
          />
          {claimedActions.length > 0 && (
            <p
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-secondary)',
                lineHeight: 'var(--leading-relaxed)',
                marginBottom: 'var(--space-4)',
              }}
            >
              LUMINA noticed phrases in the transcript that suggest an action may have
              already happened. This is an unconfirmed signal — please confirm below
              only if you actually did it.
            </p>
          )}
          {claimedActions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
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
          <p
            style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--lumina-text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
              marginBottom: 'var(--space-4)',
            }}
          >
            Did you already share any requested information or take any requested action?
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
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
        </Card>
      )}

      {/* ---- INCIDENT TIMELINE ---- */}
      {incident.timeline.length > 0 && (
        <Card>
          <SectionHeader
            number={6}
            title="Incident Timeline"
            subtitle="Chronological record of events"
          />
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0,
              position: 'relative',
            }}
          >
            {incident.timeline.map((entry, i) => (
              <TimelineItem key={entry.entry_id} entry={entry} isLast={i === incident.timeline.length - 1} />
            ))}
          </div>
        </Card>
      )}

      {/* ---- ANALYZE CONVERSATION ---- */}
      <Card>
        <SectionHeader
          number={7}
          title="Analyze Conversation"
          subtitle="Upload a recording and LUMINA will transcribe and analyze it for interaction patterns"
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
            LUMINA does not automatically record your calls. Select an audio file you legitimately
            recorded (WAV, MP3, FLAC, OGG, M4A, WebM). The audio is transcribed locally,
            analyzed for interaction patterns, and not retained after processing.
          </p>

          <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              id="audio-file-input"
              type="file"
              accept=".wav,.mp3,.flac,.ogg,.m4a,.webm,audio/wav,audio/mpeg,audio/flac,audio/ogg,audio/mp4,audio/webm"
              onChange={handleFileChange}
              style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}
            />
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

          {selectedAudioFile && (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{selectedAudioFile.name}</span>
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
            <div role="alert" style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-danger)', lineHeight: 'var(--leading-relaxed)' }}>
              {uploadError}
            </div>
          )}

          {/* Streaming session status */}
          {(streaming.state.isRecording || streaming.state.status === 'PROCESSING' || streaming.state.status === 'COMPLETE') && (
            <div style={{
              padding: 'var(--space-3)',
              background: 'rgba(0, 0, 0, 0.15)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--lumina-border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-2)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--lumina-text)' }}>
                  {streaming.state.status === 'CAPTURING' && 'Recording microphone audio…'}
                  {streaming.state.status === 'PROCESSING' && 'Processing audio chunk…'}
                  {streaming.state.status === 'COMPLETE' && 'Recording complete'}
                  {streaming.state.status === 'ERROR' && 'Recording error'}
                </span>
                {streaming.state.isRecording && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={streaming.stopRecording}
                  >
                    Stop & Analyze
                  </Button>
                )}
                {(streaming.state.isRecording || streaming.state.status === 'PROCESSING') && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={streaming.abortRecording}
                  >
                    Cancel
                  </Button>
                )}
              </div>
              {streaming.state.status === 'CAPTURING' && (
                <div style={{ display: 'flex', gap: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)' }}>
                  <span>Chunks: {streaming.state.totalChunks}</span>
                  <span>Segments: {streaming.state.totalSegments}</span>
                  <span>Observations: {streaming.state.totalObservations}</span>
                </div>
              )}
              {streaming.state.status === 'COMPLETE' && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-system)' }}>
                  {streaming.state.totalSegments} transcript segment(s) produced from {streaming.state.totalChunks} chunk(s).
                  {streaming.state.totalObservations > 0 && (
                    <> {streaming.state.totalObservations} observation(s) identified.</>
                  )}
                </div>
              )}
              {streaming.state.error && (
                <div role="alert" style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-danger)' }}>
                  {streaming.state.error}
                </div>
              )}
            </div>
          )}

          {uploadResult && !uploadError && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div role="status" style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-system)' }}>
                Conversation analyzed. Transcript and observations added to incident.
              </div>
              {uploadResult.transcription && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  model: {uploadResult.transcription.model} · device: {uploadResult.transcription.device} · lang: {uploadResult.transcription.language}
                  {typeof uploadResult.transcription.duration_seconds === 'number' && (
                    <> · audio: {uploadResult.transcription.duration_seconds.toFixed(1)}s</>
                  )}
                </div>
              )}

              {/* Timestamped transcribed segments */}
              {uploadedSegments.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: 'var(--tracking-wider)', textTransform: 'uppercase', color: 'var(--lumina-text-muted)' }}>
                    What LUMINA heard
                  </div>
                  {uploadedSegments.map((seg) => (
                    <div
                      key={seg.segment_id}
                      style={{
                        padding: 'var(--space-3)',
                        background: 'rgba(0, 0, 0, 0.15)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--lumina-border-subtle)',
                        display: 'flex',
                        gap: 'var(--space-3)',
                        alignItems: 'flex-start',
                      }}
                    >
                      {(seg.start_time !== undefined || seg.end_time !== undefined) && (
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', flexShrink: 0, paddingTop: '0.1rem' }}>
                          {seg.start_time !== undefined ? `${seg.start_time.toFixed(1)}s` : ''}
                          {seg.start_time !== undefined && seg.end_time !== undefined ? ' – ' : ''}
                          {seg.end_time !== undefined ? `${seg.end_time.toFixed(1)}s` : ''}
                        </span>
                      )}
                      {seg.speaker && seg.speaker !== 'UNKNOWN' && (
                        <span style={{
                          fontSize: 'var(--text-xs)',
                          fontWeight: 700,
                          letterSpacing: 'var(--tracking-wide)',
                          color: seg.speaker === 'CALLER' ? 'var(--lumina-warning)' : 'var(--lumina-system)',
                          flexShrink: 0,
                          paddingTop: '0.1rem',
                        }}>
                          {seg.speaker}
                        </span>
                      )}
                      {seg.speaker_attribution_method && seg.speaker_attribution_method !== 'UNKNOWN' && (
                        <span style={{
                          fontSize: 'var(--text-xs)',
                          color: 'var(--lumina-text-muted)',
                          flexShrink: 0,
                          paddingTop: '0.1rem',
                        }}>
                          {seg.speaker_attribution_method === 'STT' ? '(model)' :
                           seg.speaker_attribution_method === 'PROVIDED' ? '(provided)' :
                           seg.speaker_attribution_method === 'EXTRACTED' ? '(inferred)' : ''}
                        </span>
                      )}
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text)', lineHeight: 'var(--leading-relaxed)' }}>
                        {seg.text}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted observations */}
              {uploadResult.observations_extracted > 0 && (
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-warning)' }}>
                  {uploadResult.observations_extracted} observation(s) identified from this conversation.
                  {escalation && escalation.has_escalation && (
                    <> Escalation patterns are shown in the Conversation Escalation section above.</>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* ---- ADD MORE EVIDENCE ---- */}
      <Card>
        <SectionHeader
          number={8}
          title="Add More Evidence"
          subtitle="Paste or type what was said"
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div>
            <label
              htmlFor="transcript-source"
              style={{
                display: 'block',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Source
            </label>
            <select
              id="transcript-source"
              value={transcriptSource}
              onChange={(e) => setTranscriptSource(e.target.value as TranscriptSource)}
              style={{
                width: '100%',
                padding: 'var(--space-3)',
                background: 'var(--lumina-surface)',
                border: '1px solid var(--lumina-border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--lumina-text)',
                fontSize: 'var(--text-sm)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              <option value="USER_TYPED">User typed</option>
              <option value="USER_DICTATED">User dictated</option>
              <option value="MESSAGE_FORWARD">Message forwarded</option>
              <option value="STT_PROVIDER" disabled>
                Speech-to-text (add via audio upload below)
              </option>
            </select>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--lumina-text-muted)', marginTop: 'var(--space-2)' }}>
              Local transcription runs on your device. Transcribed segments report speaker as
              UNKNOWN — LUMINA does not perform speaker diarization.
            </div>
          </div>

          <div>
            <label
              htmlFor="transcript-text"
              style={{
                display: 'block',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                color: 'var(--lumina-text-muted)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Transcript
            </label>
            <textarea
              id="transcript-text"
              value={transcriptText}
              onChange={(e) => setTranscriptText(e.target.value)}
              placeholder="Paste or type what was said..."
              rows={5}
              style={{
                width: '100%',
                padding: 'var(--space-3)',
                background: 'var(--lumina-surface)',
                border: '1px solid var(--lumina-border)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--lumina-text)',
                fontSize: 'var(--text-sm)',
                fontFamily: 'var(--font-sans)',
                lineHeight: 'var(--leading-relaxed)',
                resize: 'vertical',
              }}
            />
          </div>

          <Button
            variant="primary"
            onClick={handleSubmitTranscript}
            disabled={!transcriptText.trim() || isSubmitting || incident.status === 'CLOSED'}
          >
            {isSubmitting ? 'Submitting…' : 'Submit Transcript'}
          </Button>

          {incident.status === 'CLOSED' && (
            <p
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--lumina-text-muted)',
                lineHeight: 'var(--leading-relaxed)',
              }}
            >
              This incident is closed. Start a new incident to add more evidence.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}

// ---- Timeline Item Component ----

function TimelineItem({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  const time = formatTimestamp(entry.timestamp);
  const typeLabels: Record<string, string> = {
    INCIDENT_CREATED: 'Incident started',
    EVIDENCE_ADDED: 'Evidence identified',
    USER_ACTION_RECORDED: 'User action recorded',
    STATE_CHANGED: 'Status changed',
    EXPOSURE_UPDATED: 'Exposure updated',
    INCIDENT_CLOSED: 'Incident closed',
  };
  const label = typeLabels[entry.entry_type] ?? entry.entry_type;

  return (
    <div
      style={{
        display: 'flex',
        gap: 'var(--space-4)',
        position: 'relative',
        paddingBottom: isLast ? 0 : 'var(--space-4)',
      }}
    >
      {/* Vertical line */}
      {!isLast && (
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            left: '3px',
            top: '12px',
            bottom: 0,
            width: '1px',
            background: 'var(--lumina-border-subtle)',
          }}
        />
      )}

      {/* Dot */}
      <div
        aria-hidden="true"
        style={{
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          background: 'var(--lumina-investigation)',
          flexShrink: 0,
          marginTop: '0.35rem',
        }}
      />

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          {time && (
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--lumina-text-muted)',
              }}
            >
              {time}
            </span>
          )}
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--lumina-text-secondary)' }}>
            {label}
          </span>
        </div>
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--lumina-text)',
            lineHeight: 'var(--leading-relaxed)',
            marginTop: 'var(--space-1)',
          }}
        >
          {entry.summary}
        </p>
        {/* Show transcript text span if available */}
        {(() => {
          const textSpan = entry.metadata?.text_span;
          if (typeof textSpan !== 'string') return null;
          return (
            <div
              style={{
                marginTop: 'var(--space-2)',
                padding: 'var(--space-2)',
                background: 'rgba(0, 0, 0, 0.15)',
                borderRadius: 'var(--radius-sm)',
                borderLeft: '2px solid var(--lumina-investigation)',
                fontSize: 'var(--text-xs)',
                fontStyle: 'italic',
                color: 'var(--lumina-text-muted)',
                lineHeight: 'var(--leading-relaxed)',
              }}
            >
              "{textSpan}"
            </div>
          );
        })()}
        {/* Show segment timestamps if available */}
        {(() => {
          const startTime = entry.metadata?.segment_start_time;
          if (typeof startTime !== 'number') return null;
          const endTime = entry.metadata?.segment_end_time;
          return (
            <span
              style={{
                display: 'inline-block',
                marginTop: 'var(--space-1)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--lumina-text-muted)',
              }}
            >
              Segment: {startTime.toFixed(1)}s
              {typeof endTime === 'number' && (
                <> – {endTime.toFixed(1)}s</>
              )}
            </span>
          );
        })()}
        {/* Show speaker if available */}
        {(() => {
          const speaker = entry.metadata?.speaker;
          if (typeof speaker !== 'string' || speaker === 'UNKNOWN') return null;
          return (
            <span
              style={{
                display: 'inline-block',
                marginTop: 'var(--space-1)',
                marginLeft: 'var(--space-2)',
                padding: '1px var(--space-2)',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                color: speaker === 'CALLER' ? 'var(--lumina-warning)' : 'var(--lumina-system)',
                background: speaker === 'CALLER'
                  ? 'rgba(245, 158, 11, 0.1)' : 'rgba(59, 130, 246, 0.1)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              {speaker}
            </span>
          );
        })()}
      </div>
    </div>
  );
}
