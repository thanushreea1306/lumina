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

export interface TranscriptSegment {
  segment_id: string;
  text: string;
  start_time?: number;
  end_time?: number;
  speaker?: 'CALLER' | 'USER' | 'UNKNOWN';
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
