/* ============================================================
   LUMINA Safety Domain Types
   ============================================================
   Strongly typed domain types matching the FastAPI backend.
   Derived from app/evidence/models.py.
   ============================================================ */

// ---- Safety States (from backend SafetyState enum) ----
export type SafetyState =
  | 'CLEAR'
  | 'WATCH'
  | 'PAUSE'
  | 'VERIFY'
  | 'PROTECT'
  | 'RECOVERY';

export const SAFETY_STATES: readonly SafetyState[] = [
  'CLEAR',
  'WATCH',
  'PAUSE',
  'VERIFY',
  'PROTECT',
  'RECOVERY',
] as const;

export const SAFETY_STATE_LABELS: Record<SafetyState, string> = {
  CLEAR: 'Clear',
  WATCH: 'Watch',
  PAUSE: 'Pause',
  VERIFY: 'Verify',
  PROTECT: 'Protect',
  RECOVERY: 'Recovery',
};

// Maps safety state to its semantic color token CSS variable name
export const SAFETY_STATE_COLORS: Record<SafetyState, string> = {
  CLEAR: 'var(--lumina-recovery)',
  WATCH: 'var(--lumina-warning)',
  PAUSE: 'var(--lumina-danger)',
  VERIFY: 'var(--lumina-warning)',
  PROTECT: 'var(--lumina-danger)',
  RECOVERY: 'var(--lumina-investigation)',
};

// ---- Evidence Status (from backend EvidenceStatus enum) ----
export type EvidenceStatus =
  | 'OBSERVED'
  | 'USER_CONFIRMED'
  | 'UNKNOWN'
  | 'NOT_AVAILABLE'
  | 'NOT_PERMITTED'
  | 'INFERRED';

export const EVIDENCE_STATUSES: readonly EvidenceStatus[] = [
  'OBSERVED',
  'USER_CONFIRMED',
  'UNKNOWN',
  'NOT_AVAILABLE',
  'NOT_PERMITTED',
  'INFERRED',
] as const;

export const EVIDENCE_STATUS_LABELS: Record<EvidenceStatus, string> = {
  OBSERVED: 'Observed',
  USER_CONFIRMED: 'User Confirmed',
  UNKNOWN: 'Unknown',
  NOT_AVAILABLE: 'Not Available',
  NOT_PERMITTED: 'Not Permitted',
  INFERRED: 'Inferred',
};

// ---- Evidence Sources (from backend EvidenceSource enum) ----
export type EvidenceSource =
  | 'DEVICE'
  | 'USER'
  | 'SYSTEM'
  | 'MODEL'
  | 'RULE';

export const EVIDENCE_SOURCES: readonly EvidenceSource[] = [
  'DEVICE',
  'USER',
  'SYSTEM',
  'MODEL',
  'RULE',
] as const;

export const EVIDENCE_SOURCE_LABELS: Record<EvidenceSource, string> = {
  DEVICE: 'Device',
  USER: 'User',
  SYSTEM: 'System',
  MODEL: 'Model',
  RULE: 'Rule',
};

// ---- Timeline Event Types (from backend TimelineEventType) ----
export type TimelineEventType =
  | 'SESSION_STARTED'
  | 'CALL_STARTED'
  | 'CALL_ACTIVE'
  | 'USER_OBSERVATION'
  | 'HIGH_RISK_ACTION_REQUEST'
  | 'USER_RESPONSE'
  | 'CALL_ENDED'
  | 'DECISION';

// ---- User Observation Types (from backend UserObservationType) ----
export type UserObservationType =
  | 'AUTHORITY_CLAIM'
  | 'THREAT_OF_ARREST'
  | 'THREAT_OF_LEGAL_ACTION'
  | 'URGENCY'
  | 'SECRECY_REQUEST'
  | 'MONEY_REQUEST'
  | 'OTP_REQUEST'
  | 'PASSWORD_REQUEST'
  | 'IDENTITY_DOCUMENT_REQUEST'
  | 'REMOTE_ACCESS_REQUEST'
  | 'APP_INSTALL_REQUEST'
  | 'BANK_TRANSFER_REQUEST'
  | 'CRYPTO_REQUEST'
  | 'GIFT_CARD_REQUEST'
  | 'CALL_BACK_INSTRUCTION'
  | 'INDEPENDENT_VERIFICATION_BLOCKED';

// ---- High Risk Action Types (from backend HighRiskActionType) ----
export type HighRiskActionType =
  | 'SEND_MONEY'
  | 'SHARE_OTP'
  | 'SHARE_PASSWORD'
  | 'SHARE_CREDENTIAL'
  | 'SHARE_ID_DOCUMENT'
  | 'INSTALL_REMOTE_ACCESS'
  | 'GRANT_REMOTE_CONTROL'
  | 'TRANSFER_CRYPTO'
  | 'SHARE_BANK_DETAILS';

// ---- Action Status (from backend ActionStatus) ----
export type ActionStatus =
  | 'REQUESTED'
  | 'PERFORMED'
  | 'DECLINED'
  | 'PAUSED'
  | 'UNKNOWN';

// ---- Evidence Record ----
export interface Evidence {
  evidence_id: string;
  session_id: string;
  type: string;
  value: unknown;
  status: EvidenceStatus;
  source: EvidenceSource;
  timestamp: string;
  sequence: number;
  confidence: number | null;
  metadata: Record<string, unknown>;
}

// ---- Timeline Event ----
export interface TimelineEvent {
  session_id: string;
  event_type: TimelineEventType;
  sequence: number;
  timestamp: string;
  payload: Record<string, unknown>;
}

// ---- High Risk Action Instance ----
export interface HighRiskActionInstance {
  action: HighRiskActionType;
  status: ActionStatus;
  reversibility: 'IRREVERSIBLE' | 'HARD_TO_REVERSE' | 'REVERSIBLE';
  impact: string[];
  urgency: 'IMMEDIATE' | 'HIGH' | 'MODERATE';
  verifiable_independently: boolean;
  trusted_person_intervention_helps: boolean;
  description: string;
  related_observation_types: UserObservationType[];
  session_id: string;
  timestamp: string;
  sequence: number;
}

// ---- Supporting Evidence (for decision) ----
export interface SupportingEvidence {
  type: string;
  status: string;
  source: string;
  value: unknown;
  timestamp: string;
}

// ---- Safety Decision (from backend SafetyDecision) ----
export interface SafetyDecision {
  session_id: string;
  state: SafetyState;
  state_label: string;
  reason_codes: string[];
  supporting_evidence: SupportingEvidence[];
  missing_information: string[];
  recommended_action: string;
  uncertainty: string[];
}

// ---- Decision Context (from backend DecisionContext) ----
export interface DecisionContext {
  session_id: string;
  duration_seconds: number | null;
  call_started: boolean;
  call_ended: boolean;
  observations: UserObservationType[];
  high_risk_actions: HighRiskActionInstance[];
  evidence_count: number;
  missing_information: string[];
  user_response: Array<{ action: string; response: string; timestamp: string }>;
  has_requested_high_risk_action: boolean;
  has_performed_high_risk_action: boolean;
  protective_actions_possible: string[];
}

// ---- Decision Response (from GET /api/sessions/{id}/decision) ----
export interface DecisionResponse {
  session_id: string;
  decision: SafetyDecision;
  context: DecisionContext;
}

// ---- Session Data ----
export interface SessionData {
  session_id: string;
  started_at: string;
  events: TimelineEvent[];
  evidence: Evidence[];
}
