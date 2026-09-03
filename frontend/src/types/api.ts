/* ============================================================
   LUMINA API Types
   ============================================================
   Request and response types for the FastAPI backend.
   Derived directly from app/evidence/router.py Pydantic models.
   ============================================================ */

// ---- API Error ----
export interface ApiError {
  detail: string;
}

// ---- API Response Wrapper ----
export type ApiResponse<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; error: string };

// ---- Device Registration ----
// POST /api/devices/register
// Request body: {} (no input needed)
// Response:
export interface RegisterDeviceResponse {
  device_id: string;
  device_secret: string;
  message: string;
}

// ---- Create Session ----
// POST /api/sessions
// Request body:
export interface CreateSessionRequest {
  started_at?: string;
}
// Response:
export interface CreateSessionResponse {
  session_id: string;
  started_at: string;
}

// ---- Append Event ----
// POST /api/sessions/{session_id}/events
// Request body:
export interface AppendEventRequest {
  event_type: string;
  payload?: Record<string, unknown>;
  event_id?: string;
  source?: string;
}
// Response:
export interface AppendEventResponse {
  session_id: string;
  event_type: string;
  sequence: number;
  timestamp: string;
  payload: Record<string, unknown>;
}

// ---- Add Observation ----
// POST /api/sessions/{session_id}/observations
// Request body:
export interface AddObservationRequest {
  observation_type: string;
  notes?: string;
}
// Response:
export interface AddObservationResponse {
  evidence_id: string;
  session_id: string;
  type: string;
  value: unknown;
  status: string;
  source: string;
  timestamp: string;
  sequence: number;
  confidence: number | null;
  metadata: Record<string, unknown>;
}

// ---- Get Session ----
// GET /api/sessions/{session_id}
// Response:
export interface GetSessionResponse {
  session_id: string;
  started_at: string;
  events: Array<{
    session_id: string;
    event_type: string;
    sequence: number;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
  evidence: Array<{
    evidence_id: string;
    session_id: string;
    type: string;
    value: unknown;
    status: string;
    source: string;
    timestamp: string;
    sequence: number;
    confidence: number | null;
    metadata: Record<string, unknown>;
  }>;
}

// ---- Get Decision ----
// GET /api/sessions/{session_id}/decision
// Response:
export interface GetDecisionResponse {
  session_id: string;
  decision: {
    session_id: string;
    state: string;
    state_label: string;
    reason_codes: string[];
    supporting_evidence: Array<{
      type: string;
      status: string;
      source: string;
      value: unknown;
      timestamp: string;
    }>;
    missing_information: string[];
    recommended_action: string;
    uncertainty: string[];
  };
  context: {
    session_id: string;
    duration_seconds: number | null;
    call_started: boolean;
    call_ended: boolean;
    observations: string[];
    high_risk_actions: Array<Record<string, unknown>>;
    evidence_count: number;
    missing_information: string[];
    user_response: Array<Record<string, unknown>>;
    has_requested_high_risk_action: boolean;
    has_performed_high_risk_action: boolean;
    protective_actions_possible: string[];
  };
}

// ---- Record Outcome ----
// POST /api/sessions/{session_id}/outcome
// Request body:
export interface RecordOutcomeRequest {
  outcome: string;
}
// Response:
export interface RecordOutcomeResponse {
  session_id: string;
  outcome: string;
}

// ---- User Response ----
// POST /api/sessions/{session_id}/respond
// Request body:
export interface UserResponseRequest {
  action: string;
  response: string;
}
// Response:
export interface UserResponseResponse {
  evidence_id: string;
  session_id: string;
  type: string;
  value: unknown;
  status: string;
  source: string;
  timestamp: string;
  sequence: number;
  confidence: number | null;
  metadata: Record<string, unknown>;
}
