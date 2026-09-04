/* ============================================================
   LUMINA Streaming Session API Client
   ============================================================
   Client-side API for streaming audio chunks to LUMINA.

   Uses the existing HMAC authentication infrastructure via device.ts.
   Audio chunks are sent as multipart form data.
   ============================================================ */

import { DEFAULT_BASE_URL } from './client';
import { generateAuthHeaders, ensureDeviceIdentity } from './device';
import type {
  StartStreamResponse,
  StreamChunkResponse,
  FinishStreamResponse,
  AbortStreamResponse,
} from '@/types/incident';

/**
 * Generate authenticated headers for a streaming API request.
 */
async function authHeaders(method: string, path: string): Promise<Record<string, string>> {
  const creds = await ensureDeviceIdentity();
  if (!creds.ok) throw new Error('Device authentication required');
  return generateAuthHeaders(creds.data, method, path);
}

// ---- Start a streaming session ----

export async function startStream(
  incidentId: string,
): Promise<StartStreamResponse> {
  const path = `/api/incidents/${incidentId}/stream/start`;
  const method = 'POST';
  const headers = await authHeaders(method, path);

  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers: { ...headers, 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Stream start failed (${response.status}): ${detail}`);
  }
  return response.json();
}

// ---- Upload an audio chunk ----

export async function uploadStreamChunk(
  incidentId: string,
  sessionId: string,
  audioBlob: Blob,
  sequence: number,
  mediaType: string = 'audio/webm',
  durationSeconds?: number,
): Promise<StreamChunkResponse> {
  const path = `/api/incidents/${incidentId}/stream/chunk`;
  const method = 'POST';
  const headers = await authHeaders(method, path);

  const formData = new FormData();
  formData.append('audio', audioBlob, `chunk-${sequence}.webm`);
  formData.append('sequence', String(sequence));
  formData.append('media_type', mediaType);
  if (durationSeconds !== undefined) {
    formData.append('duration_seconds', String(durationSeconds));
  }

  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers: { ...headers, 'X-Stream-Session-ID': sessionId },
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Chunk upload failed (${response.status}): ${detail}`);
  }
  return response.json();
}

// ---- Finish a streaming session ----

export async function finishStream(
  incidentId: string,
  sessionId: string,
): Promise<FinishStreamResponse> {
  const path = `/api/incidents/${incidentId}/stream/finish`;
  const method = 'POST';
  const headers = await authHeaders(method, path);

  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers: { ...headers, 'Content-Type': 'application/json', 'X-Stream-Session-ID': sessionId },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Stream finish failed (${response.status}): ${detail}`);
  }
  return response.json();
}

// ---- Abort a streaming session ----

export async function abortStream(
  incidentId: string,
  sessionId: string,
): Promise<AbortStreamResponse> {
  const path = `/api/incidents/${incidentId}/stream/abort`;
  const method = 'POST';
  const headers = await authHeaders(method, path);

  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method,
    headers: { ...headers, 'Content-Type': 'application/json', 'X-Stream-Session-ID': sessionId },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Stream abort failed (${response.status}): ${detail}`);
  }
  return response.json();
}

// ---- Browser MediaRecorder Helper ----

/**
 * Start capturing audio from the browser microphone using MediaRecorder.
 *
 * IMPORTANT: This captures microphone audio only. It does NOT capture
 * the remote side of a phone call. The UI must clearly communicate
 * what is being recorded.
 *
 * Returns a MediaRecorder and the MediaStream for cleanup.
 */
export async function startMicrophoneCapture(): Promise<{
  recorder: MediaRecorder;
  stream: MediaStream;
}> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  // Determine the best supported MIME type
  const mimeTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
    'audio/wav',
  ];

  let mimeType = '';
  for (const type of mimeTypes) {
    if (MediaRecorder.isTypeSupported(type)) {
      mimeType = type;
      break;
    }
  }

  const recorder = new MediaRecorder(stream, {
    mimeType: mimeType || undefined,
  });

  return { recorder, stream };
}

/**
 * Stop capturing audio and clean up MediaStream tracks.
 */
export function stopCapture(recorder: MediaRecorder, stream: MediaStream): void {
  if (recorder.state !== 'inactive') {
    recorder.stop();
  }
  // Release all tracks to stop the microphone
  stream.getTracks().forEach((track) => track.stop());
}
