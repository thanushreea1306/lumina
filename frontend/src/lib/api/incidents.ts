/* ============================================================
   LUMINA Incidents API
   ============================================================
   Typed API calls for incident endpoints.
   All calls require device authentication headers.
   ============================================================ */

import { apiGet, apiPost } from './client';
import { generateAuthHeaders } from './device';
import type { ApiResponse } from '@/types/api';
import type {
  CreateIncidentRequest,
  CreateIncidentResponse,
  AddIncidentEvidenceRequest,
  AddIncidentEvidenceResponse,
  RecordIncidentActionRequest,
  RecordIncidentActionResponse,
  GetIncidentResponse,
  GetIncidentNextActionResponse,
  ListIncidentsResponse,
  AddTranscriptRequest,
  AddTranscriptResponse,
  AddTranscriptBatchRequest,
  AddTranscriptBatchResponse,
  CloseIncidentRequest,
  CloseIncidentResponse,
  UploadAudioResponse,
} from '@/types/incident';
import type { DeviceCredentials } from './device';

// ---- Helper ----
function getIncidentPath(incidentId: string, suffix?: string): string {
  const base = `/api/incidents/${incidentId}`;
  return suffix ? `${base}/${suffix}` : base;
}

// ---- Create Incident ----
export async function createIncident(
  credentials: DeviceCredentials,
  request?: CreateIncidentRequest,
): Promise<ApiResponse<CreateIncidentResponse>> {
  const path = '/api/incidents';
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<CreateIncidentResponse>(path, request ?? {}, headers);
}

// ---- List Incidents ----
export async function listIncidents(
  credentials: DeviceCredentials,
  limit = 50,
): Promise<ApiResponse<ListIncidentsResponse>> {
  // The URL carries the ?limit= query, but the HMAC signature must be
  // computed over the pathname only (no query), matching the backend which
  // verifies over str(request.url.path).
  const pathname = '/api/incidents';
  const path = `${pathname}?limit=${limit}`;
  const headers = await generateAuthHeaders(credentials, 'GET', pathname);
  return apiGet<ListIncidentsResponse>(path, headers);
}

// ---- Get Incident ----
export async function getIncident(
  credentials: DeviceCredentials,
  incidentId: string,
): Promise<ApiResponse<GetIncidentResponse>> {
  const path = getIncidentPath(incidentId);
  const headers = await generateAuthHeaders(credentials, 'GET', path);
  return apiGet<GetIncidentResponse>(path, headers);
}

// ---- Add Evidence ----
export async function addIncidentEvidence(
  credentials: DeviceCredentials,
  incidentId: string,
  request: AddIncidentEvidenceRequest,
): Promise<ApiResponse<AddIncidentEvidenceResponse>> {
  const path = getIncidentPath(incidentId, 'evidence');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<AddIncidentEvidenceResponse>(path, request, headers);
}

// ---- Record Action ----
export async function recordIncidentAction(
  credentials: DeviceCredentials,
  incidentId: string,
  request: RecordIncidentActionRequest,
): Promise<ApiResponse<RecordIncidentActionResponse>> {
  const path = getIncidentPath(incidentId, 'actions');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<RecordIncidentActionResponse>(path, request, headers);
}

// ---- Get Next Action ----
export async function getIncidentNextAction(
  credentials: DeviceCredentials,
  incidentId: string,
): Promise<ApiResponse<GetIncidentNextActionResponse>> {
  const path = getIncidentPath(incidentId, 'next-action');
  const headers = await generateAuthHeaders(credentials, 'GET', path);
  return apiGet<GetIncidentNextActionResponse>(path, headers);
}

// ---- Close / Archive Incident ----
export async function closeIncident(
  credentials: DeviceCredentials,
  incidentId: string,
  request?: CloseIncidentRequest,
): Promise<ApiResponse<CloseIncidentResponse>> {
  const path = getIncidentPath(incidentId, 'close');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<CloseIncidentResponse>(path, request ?? {}, headers);
}

// ---- Add Transcript ----
export async function addIncidentTranscript(
  credentials: DeviceCredentials,
  incidentId: string,
  request: AddTranscriptRequest,
): Promise<ApiResponse<AddTranscriptResponse>> {
  const path = getIncidentPath(incidentId, 'transcript');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<AddTranscriptResponse>(path, request, headers);
}

// ---- Add Transcript Segments ----
export async function addIncidentTranscriptSegments(
  credentials: DeviceCredentials,
  incidentId: string,
  request: AddTranscriptBatchRequest,
): Promise<ApiResponse<AddTranscriptBatchResponse>> {
  const path = getIncidentPath(incidentId, 'transcript/segments');
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<AddTranscriptBatchResponse>(path, request, headers);
}

// ---- Upload Audio for STT ----
// Uses multipart/form-data (not JSON), so builds its own fetch.
export async function uploadIncidentAudio(
  credentials: DeviceCredentials,
  incidentId: string,
  file: File,
): Promise<ApiResponse<UploadAudioResponse>> {
  const path = getIncidentPath(incidentId, 'audio');
  const headers = await generateAuthHeaders(credentials, 'POST', path);

  // Base is the backend origin WITHOUT /api (see client.ts); empty in dev.
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const url = `${baseUrl}${path}`;

  try {
    const formData = new FormData();
    formData.append('audio', file, file.name);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        ...headers,
        // No Content-Type header — browser sets multipart boundary automatically
      },
      // Longer timeout: local transcription can take longer than 15s
      signal: AbortSignal.timeout(120_000),
      body: formData,
    });

    if (!response.ok) {
      let errorDetail: string;
      try {
        const errorBody = await response.json();
        errorDetail = errorBody.detail ?? `HTTP ${response.status}`;
      } catch {
        errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      }
      return { ok: false, status: response.status, error: errorDetail };
    }

    const data: UploadAudioResponse = await response.json();
    return { ok: true, data };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Network request failed';
    return { ok: false, status: 0, error: message };
  }
}
