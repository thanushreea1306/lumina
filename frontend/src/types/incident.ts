/* ============================================================
   LUMINA Incident Domain Types
   ============================================================
   Types for the Digital Incident Copilot.
   Derived from app/incident/models.py.

   These are INTERNAL types — not exposed to users in UI text.
   The frontend uses these for data flow only.
   ============================================================ */

// ---- Epistemic Status ----
export type EpistemicStatus = 'FACT' | 'INFERENCE' | 'UNKNOWN' | 'ACTION';

// ---- Exposure ----
export type ExposureCategory =
  | 'MONEY'
  | 'ACCOUNT'
  | 'AUTHENTICATION'
  | 'DEVICE'
  | 'IDENTITY'
  | 'PERSONAL_INFORMATION'
  | 'UNKNOWN';

export type ExposureLevel =
  | 'NOT_INDICATED'
  | 'POTENTIALLY_EXPOSED'
  | 'USER_CONFIRMED_EXPOSED'
  | 'UNKNOWN';

export interface ExposureState {
  category: ExposureCategory;
  level: ExposureLevel;
  evidence_basis: string;
  updated_at: string;
}

// ---- User Action ----
export type UserActionType =
  | 'SHARED_OTP'
  | 'SHARED_PASSWORD'
  | 'SHARED_PERSONAL_INFORMATION'
  | 'SHARED_DOCUMENT'
  | 'SENT_MONEY'
  | 'CLICKED_LINK'
  | 'INSTALLED_APPLICATION'
  | 'GRANTED_REMOTE_ACCESS'
  | 'LOGGED_IN'
  | 'DECLINED_REQUEST'
  | 'UNKNOWN_ACTION';

export interface UserAction {
  action_id: string;
  action_type: UserActionType;
  description: string;
  timestamp: string;
  sequence: number;
}

// ---- Incident Status ----
export type IncidentStatus =
  | 'ACTIVE'
  | 'MONITORING'
  | 'ACTION_REQUIRED'
  | 'RECOVERING'
  | 'CLOSED'
  | 'UNKNOWN';

// ---- Priority ----
export type Priority = 'IMMEDIATE' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';

// ---- Timeline ----
export type TimelineEntryType =
  | 'EVIDENCE_ADDED'
  | 'USER_ACTION_RECORDED'
  | 'STATE_CHANGED'
  | 'EXPOSURE_UPDATED'
  | 'INCIDENT_CREATED'
  | 'INCIDENT_CLOSED';

export interface TimelineEntry {
  entry_id: string;
  entry_type: TimelineEntryType;
  sequence: number;
  timestamp: string;
  summary: string;
  epistemic_status: EpistemicStatus;
  metadata: Record<string, unknown>;
}

// ---- Recommended Action ----
export interface RecommendedAction {
  action: string;
  reason: string;
  evidence_basis: string[];
  urgency: Priority;
  official_channel_guidance?: string;
}

// ---- Incident ----
export interface Incident {
  incident_id: string;
  created_at: string;
  updated_at: string;
  status: IncidentStatus;
  timeline: TimelineEntry[];
  user_actions: UserAction[];
  exposure: Record<ExposureCategory, ExposureState>;
  unknowns: string[];
  priority: Priority;
  next_action: RecommendedAction | null;
  session_ids: string[];
  metadata: Record<string, unknown>;
}

// ---- API Request/Response Types ----

export interface CreateIncidentRequest {
  session_id?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateIncidentResponse {
  incident_id: string;
  created_at: string;
  status: IncidentStatus;
  priority: Priority;
}

export interface AddIncidentEvidenceRequest {
  observation_type: string;
  notes?: string;
}

export interface AddIncidentEvidenceResponse {
  incident_id: string;
  status: IncidentStatus;
  priority: Priority;
  timeline_count: number;
  next_action: RecommendedAction | null;
}

export interface RecordIncidentActionRequest {
  action_type: string;
  description: string;
}

export interface RecordIncidentActionResponse {
  incident_id: string;
  status: IncidentStatus;
  priority: Priority;
  action_count: number;
  next_action: RecommendedAction | null;
}

export interface GetIncidentResponse extends Incident {}

export interface GetIncidentNextActionResponse {
  incident_id: string;
  next_action: RecommendedAction | null;
  message?: string;
}

export interface ListIncidentsResponse {
  total: number;
  incidents: Array<{
    incident_id: string;
    created_at: string;
    updated_at: string;
    status: IncidentStatus;
    priority: Priority;
  }>;
}

// ---- Transcript Types ----

export type TranscriptSource = 'USER_TYPED' | 'USER_DICTATED' | 'STT_PROVIDER' | 'MESSAGE_FORWARD';

export type SpeakerAttributionMethod = 'EXTRACTED' | 'PROVIDED' | 'STT' | 'UNKNOWN';
export type SpeakerEpistemicStatus = 'ESTABLISHED' | 'INFERRED' | 'UNKNOWN';

export interface TranscriptSegment {
  segment_id: string;
  text: string;
  start_time?: number;
  end_time?: number;
  speaker?: 'CALLER' | 'USER' | 'UNKNOWN';
  speaker_attribution_method?: SpeakerAttributionMethod;
  speaker_epistemic_status?: SpeakerEpistemicStatus;
  source_provider: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface ExtractedObservation {
  observation_type: string;
  confidence_in_extraction: number;
  text_span: string;
  span_start: number;
  span_end: number;
  extraction_method: string;
  epistemic_note: string;
}

export interface ExtractedAction {
  action_type: string;
  description: string;
  text_span: string;
  span_start: number;
  span_end: number;
  extraction_method: string;
}

export interface ExtractionResult {
  transcript_id: string;
  observations: ExtractedObservation[];
  user_actions: ExtractedAction[];
  raw_text: string;
  extraction_timestamp: string;
}

export interface AddTranscriptRequest {
  text: string;
  source?: TranscriptSource;
  batch_id?: string;
}

export interface AddTranscriptResponse {
  incident_id: string;
  status: IncidentStatus;
  priority: Priority;
  transcript_id: string;
  observations_extracted: number;
  actions_extracted: number;
  extraction: ExtractionResult;
  next_action: RecommendedAction | null;
  timeline_count: number;
}

// ---- Segment Batch Types ----

export interface TranscriptSegmentData {
  text: string;
  start_time?: number;
  end_time?: number;
  speaker?: 'CALLER' | 'USER' | 'UNKNOWN';
  segment_id?: string;
  metadata?: Record<string, unknown>;
}

export interface AddTranscriptBatchRequest {
  segments: TranscriptSegmentData[];
  full_text?: string;
  source?: TranscriptSource;
  batch_id?: string;
}

export interface AddTranscriptBatchResponse {
  incident_id: string;
  status: IncidentStatus;
  priority: Priority;
  transcript_id: string;
  segments_accepted: number;
  observations_extracted: number;
  actions_extracted: number;
  extraction: ExtractionResult;
  next_action: RecommendedAction | null;
  timeline_count: number;
}

// ---- Close / Archive Incident ----

export interface CloseIncidentRequest {
  reason?: string;
}

export interface CloseIncidentResponse {
  incident_id: string;
  status: IncidentStatus;
  closed: boolean;
  timeline_count: number;
}

// ---- Audio Transcription Types ----

export interface AudioTranscriptionInfo {
  model: string;
  device: string;
  language: string;
  duration_seconds?: number | null;
}

export interface UploadAudioResponse {
  incident_id: string;
  status: IncidentStatus;
  priority: Priority;
  transcript_id: string;
  segments_accepted: number;
  observations_extracted: number;
  actions_extracted: number;
  extraction: ExtractionResult;
  segments: TranscriptSegment[];
  next_action: RecommendedAction | null;
  timeline_count: number;
  transcription: AudioTranscriptionInfo;
}

// ---- Escalation Types (CP-13) ----

export type EscalationStage = 'SETUP' | 'PRESSURE' | 'EXTRACTION';

export type PatternStatus = 'PROGRESSING' | 'COMPLETE' | 'STATIC';

export interface EscalationEvent {
  timeline_entry_id: string;
  sequence: number;
  timestamp: string;
  observation_type: string;
  text_span: string;
}

export interface EscalationPattern {
  pattern_id: string;
  pattern_name: string;
  stages_matched: string[];
  stage: EscalationStage;
  status: PatternStatus;
  evidence_events: EscalationEvent[];
  explanation: string;
  first_detected_at: string;
  last_updated_at: string;
  epistemic_status: string;
}

export interface RepeatedRequest {
  request_type: string;
  count: number;
  event_count: number;
  explanation: string;
  epistemic_status: string;
}

export interface EscalationResult {
  patterns: EscalationPattern[];
  repeated_requests: RepeatedRequest[];
  overall_stage: EscalationStage;
  has_escalation: boolean;
  evidence_basis: string[];
  epistemic_status: string;
}

// ---- Streaming Types (CP-15) ----

export type SessionStatus =
  | 'IDLE'
  | 'CAPTURING'
  | 'PROCESSING'
  | 'PAUSED'
  | 'COMPLETE'
  | 'ERROR'
  | 'ABORTED';

export interface StartStreamResponse {
  session_id: string;
  incident_id: string;
  status: SessionStatus;
  message: string;
}

export interface StreamChunkResponse {
  session_id: string;
  chunk_sequence: number;
  accepted: boolean;
  reason?: string;
  segments_produced?: number;
  new_observations?: number;
  new_actions?: number;
  total_segments?: number;
  total_observations?: number;
}

export interface FinishStreamResponse {
  session_id: string;
  incident_id: string;
  status: SessionStatus;
  total_chunks: number;
  total_segments: number;
  total_observations: number;
  total_duration_seconds: number;
}

export interface AbortStreamResponse {
  session_id: string;
  status: string;
  total_segments?: number;
}

export interface StreamingState {
  status: SessionStatus;
  sessionId: string | null;
  isRecording: boolean;
  totalChunks: number;
  totalSegments: number;
  totalObservations: number;
  error: string | null;
  lastChunkAt: number | null;
}

// ---- Help Request Types (CP-16) ----

export type HelpUrgency = 'IMMEDIATE' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface HelpStorySection {
  heading: string;
  content: string;
  epistemic_status: string;
}

export interface HelpStory {
  incident_id: string;
  generated_at: string;
  urgency: HelpUrgency;
  one_line_summary: string;
  sections: HelpStorySection[];
  privacy_note: string;
}

export interface HelpRequestResponse {
  incident_id: string;
  help_story: HelpStory;
  help_story_text: string;
  already_requested: boolean;
  trusted_contact_notified: boolean;
  delivery_status: string;
}

// ---- Audio Source Types (CP-16) ----

export type AudioSourceType =
  | 'USER_PROVIDED_RECORDING'
  | 'MICROPHONE'
  | 'USER_DICTATED'
  | 'MESSAGE_FORWARD'
  | 'SYSTEM_CALL_AUDIO'
  | 'VOIP_CALL_AUDIO';

export type CapabilityStatus = 'AVAILABLE' | 'PARTIALLY_AVAILABLE' | 'NOT_AVAILABLE' | 'NOT_TESTED';

export type AudioSide = 'LOCAL_ONLY' | 'REMOTE_ONLY' | 'BOTH_SIDES' | 'UNKNOWN';

export interface AudioSourceCapability {
  source_type: AudioSourceType;
  platform: string;
  status: CapabilityStatus;
  audio_side: AudioSide;
  requires_permission: string;
  android_version_constraint?: string;
  notes: string;
}

// ---- Trusted Contact Types (CP-17) ----

export type DeliveryChannel = 'SMS' | 'EMAIL' | 'NONE';

export type HelpRequestLifecycleStatus =
  | 'NOT_CONFIGURED'
  | 'AUTHORIZED'
  | 'REQUESTED'
  | 'QUEUED'
  | 'SENDING'
  | 'SENT'
  | 'DELIVERED'
  | 'FAILED'
  | 'UNKNOWN';

export interface TrustedContactConfig {
  contact_id: string;
  display_name: string;
  delivery_channel: DeliveryChannel;
  destination_masked?: string;
  enabled: boolean;
  automatic_help_enabled: boolean;
  configured_at: string;
  updated_at: string;
}

export interface ConfigureTrustedContactRequest {
  display_name: string;
  delivery_channel: DeliveryChannel;
  destination: string;
  automatic_help_enabled?: boolean;
}

export interface HelpPolicyConfig {
  automatic_detection_enabled: boolean;
  automatic_help_request_enabled: boolean;
  auto_help_threshold: string;
}

export interface TrustedContactResponse {
  configured: boolean;
  contact: TrustedContactConfig | null;
}

export interface HelpRequestResponse {
  incident_id: string;
  help_story: HelpStory;
  help_story_text: string;
  already_requested: boolean;
  request_id?: string;
  request_status?: string;
  delivery_status: string;
  trusted_contact_configured: boolean;
  delivery_channel?: string;
}
