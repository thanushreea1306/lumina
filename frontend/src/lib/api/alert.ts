/* ============================================================
   LUMINA Alert API
   ============================================================
   Typed API call for the legacy send-alert endpoint.
   NOTE: This endpoint uses the risk engine, NOT the evidence
   framework. It requires elder_name and CallFeatures.
   ============================================================ */

import { apiPost } from './client';
import { generateAuthHeaders } from './device';
import type { ApiResponse } from '@/types/api';
import type { DeviceCredentials } from './device';

// ---- Alert Types ----

export interface SendAlertRequest {
  elder_name: string;
  // CallFeatures fields
  call_duration_min?: number;
  is_video_call?: boolean;
  is_speaker?: boolean;
  app_in_foreground?: boolean;
  number_of_apps?: number;
  call_log_count?: number;
  unknown_number?: boolean;
}

export interface SendAlertResponse {
  status: string;
  alert_sent: boolean;
  delivered: boolean;
  delivery_status: string;
  message: string | null;
  reason: string | null;
  timestamp?: string;
}

// ---- Send Alert ----

export async function sendAlert(
  credentials: DeviceCredentials,
  request: SendAlertRequest,
): Promise<ApiResponse<SendAlertResponse>> {
  const path = '/send-alert';
  const headers = await generateAuthHeaders(credentials, 'POST', path);
  return apiPost<SendAlertResponse>(path, request, headers);
}
