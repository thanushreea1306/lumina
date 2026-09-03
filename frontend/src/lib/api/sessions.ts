/* ============================================================
   LUMINA Sessions API
   ============================================================
   Typed API calls for session endpoints.
   All calls require device authentication headers.
   ============================================================ */

import { apiGet, apiPost } from './client';
import { generateAuthHeaders } from './device';
import type {
  ApiResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  AppendEventRequest,
  AppendEventResponse,
  AddObservationRequest,
  AddObservationResponse,
  GetSessionResponse,
  GetDecisionResponse,
  RecordOutcomeRequest,
  RecordOutcomeResponse,
  UserResponseRequest,
  UserResponseResponse,
} from '@/types/api';
import type { DeviceCredentials } from './device';

// ---- Helper to extract path from URL for signing ----
function getSessionPath(sessionId: string, suffix?: string): string {
  const base = `/sessions/${sessionId}`;
  return suffix ? `${base}/${suffix}` : base;
}

// ---- Create Session ----

export async function createSession(
  credentials: DeviceCredentials,
  request?: CreateSessionRequest,
): Promise<ApiResponse<CreateSessionResponse>> {
  const path = '/sessions';
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<CreateSessionResponse>(path, request ?? {}, headers);
}

// ---- Append Event ----

export async function appendEvent(
  credentials: DeviceCredentials,
  sessionId: string,
  request: AppendEventRequest,
): Promise<ApiResponse<AppendEventResponse>> {
  const path = getSessionPath(sessionId, 'events');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<AppendEventResponse>(path, request, headers);
}

// ---- Add Observation ----

export async function addObservation(
  credentials: DeviceCredentials,
  sessionId: string,
  request: AddObservationRequest,
): Promise<ApiResponse<AddObservationResponse>> {
  const path = getSessionPath(sessionId, 'observations');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<AddObservationResponse>(path, request, headers);
}

// ---- Get Session ----

export async function getSession(
  credentials: DeviceCredentials,
  sessionId: string,
): Promise<ApiResponse<GetSessionResponse>> {
  const path = getSessionPath(sessionId);
  const headers = await generateAuthHeaders(credentials, 'GET', path);
  return apiGet<GetSessionResponse>(path, headers);
}

// ---- Get Decision ----

export async function getDecision(
  credentials: DeviceCredentials,
  sessionId: string,
): Promise<ApiResponse<GetDecisionResponse>> {
  const path = getSessionPath(sessionId, 'decision');
  const headers = await generateAuthHeaders(credentials, 'GET', path);
  return apiGet<GetDecisionResponse>(path, headers);
}

// ---- Record Outcome ----

export async function recordOutcome(
  credentials: DeviceCredentials,
  sessionId: string,
  request: RecordOutcomeRequest,
): Promise<ApiResponse<RecordOutcomeResponse>> {
  const path = getSessionPath(sessionId, 'outcome');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<RecordOutcomeResponse>(path, request, headers);
}

// ---- User Response ----

export async function userResponse(
  credentials: DeviceCredentials,
  sessionId: string,
  request: UserResponseRequest,
): Promise<ApiResponse<UserResponseResponse>> {
  const path = getSessionPath(sessionId, 'respond');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<UserResponseResponse>(path, request, headers);
}
