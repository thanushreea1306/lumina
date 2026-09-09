/* ============================================================
   LUMINA Incident State Hook
   ============================================================
   Manages the Incident Copilot lifecycle: creation, transcript
   submission, incident loading, and state refresh.
   No fake data. Real backend is the source of truth.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ensureDeviceIdentity } from '@/lib/api/device';
import {
  createIncident,
  getIncident,
  addIncidentTranscript,
  recordIncidentAction,
  closeIncident,
} from '@/lib/api/incidents';
import type { DeviceCredentials } from '@/lib/api/device';
import type {
  Incident,
  IncidentStatus,
  Priority,
  ExtractionResult,
  TranscriptSource,
} from '@/types/incident';
import { isOpenIncident } from '@/types/incident';

// ---- State Types ----

export type IncidentPageStatus =
  | 'idle'
  | 'creating'
  | 'loading'
  | 'active'
  | 'submitting'
  | 'error'
  | 'unavailable';

export interface IncidentState {
  status: IncidentPageStatus;
  credentials: DeviceCredentials | null;
  incident: Incident | null;
  error: string | null;
  errorCode: number | null;
  lastExtraction: ExtractionResult | null;
  closing: boolean;
  closeError: string | null;
}

// ---- Incident ID persistence (sessionStorage) ----
const INCIDENT_STORAGE_KEY = 'lumina_current_incident_id';

// ---- Stable per-transcript idempotency key ----
// Maps a normalized transcript text to a stable batch_id for the browser
// session. Re-submitting the SAME text (e.g. a double-click or a network
// retry) reuses the SAME batch_id, so the backend deduplicates instead of
// creating duplicate transcripts/evidence. The key is content-derived — NOT a
// timestamp — so retries of the same logical submission are idempotent.
const transcriptBatchIds = new Map<string, string>();

function batchIdForText(text: string): string {
  const key = text.trim().toLowerCase();
  const existing = transcriptBatchIds.get(key);
  if (existing) return existing;
  // Content-derived, collision-resistant id: hash the text and suffix with a
  // short random token so semantically identical submissions share one id.
  const raw = `${Date.now()}|${typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2)}`;
  const hash = simpleHash(key);
  const id = `tx-${hash}-${raw.slice(-8)}`;
  transcriptBatchIds.set(key, id);
  return id;
}

function simpleHash(str: string): string {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  // Positive hex to avoid '-'
  return (h >>> 0).toString(16);
}

function getStoredIncidentId(): string | null {
  try {
    return sessionStorage.getItem(INCIDENT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeIncidentId(incidentId: string): void {
  try {
    sessionStorage.setItem(INCIDENT_STORAGE_KEY, incidentId);
  } catch { /* noop */ }
}

function clearStoredIncidentId(): void {
  try {
    sessionStorage.removeItem(INCIDENT_STORAGE_KEY);
  } catch { /* noop */ }
}

// ---- Human-readable status labels ----

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  ACTIVE: 'New incident',
  MONITORING: 'Being monitored',
  ACTION_REQUIRED: 'Needs attention',
  RECOVERING: 'Recovery in progress',
  CLOSED: 'Closed',
  UNKNOWN: 'Status unknown',
};

export const INCIDENT_PRIORITY_LABELS: Record<Priority, string> = {
  IMMEDIATE: 'Immediate',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
  NONE: 'No priority',
};

// ---- Hook ----

export function useIncidentState(pollIntervalMs = 30_000, overrideIncidentId: string | null = null) {
  const [state, setState] = useState<IncidentState>({
    status: 'idle',
    credentials: null,
    incident: null,
    error: null,
    errorCode: null,
    lastExtraction: null,
    closing: false,
    closeError: null,
  });

  const mountedRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  const fetchIncidentData = useCallback(async (
    credentials: DeviceCredentials,
    incidentId: string,
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const result = await getIncident(credentials, incidentId);
      if (!mountedRef.current || controller.signal.aborted) return;

      if (!result.ok) {
        if (result.status === 404 || result.status === 401) {
          clearStoredIncidentId();
          setState({
            status: 'idle',
            credentials,
            incident: null,
            error: null,
            errorCode: null,
            lastExtraction: null,
            closing: false,
            closeError: null,
          });
          return;
        }
        setState((prev) => ({
          ...prev,
          status: 'error',
          error: result.error,
          errorCode: result.status,
        }));
        return;
      }

      if (!controller.signal.aborted) {
        // A CLOSED or UNKNOWN incident is historical: keep it visible for this
        // view (read-only), but never let it masquerade as the *current*
        // active incident in sessionStorage.
        if (!isOpenIncident(result.data.status)) {
          clearStoredIncidentId();
        }
        setState((prev) => ({
          ...prev,
          status: 'active',
          credentials,
          incident: result.data,
          error: null,
          errorCode: null,
          lastExtraction: prev.lastExtraction,
        }));
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setState((prev) => ({
        ...prev,
        status: 'unavailable',
        error: message,
        errorCode: 0,
      }));
    }
  }, []);

  // ---- Create incident ----
  const startNewIncident = useCallback(async () => {
    setState((prev) => ({ ...prev, status: 'creating', error: null }));

    try {
      const credResult = await ensureDeviceIdentity();
      if (!mountedRef.current) return;

      if (!credResult.ok) {
        setState({
          status: 'error',
          credentials: null,
          incident: null,
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
          lastExtraction: null,
          closing: false,
          closeError: null,
        });
        return;
      }

      const credentials = credResult.data;
      const result = await createIncident(credentials);
      if (!mountedRef.current) return;

      if (!result.ok) {
        setState({
          status: 'error',
          credentials,
          incident: null,
          error: `Incident creation failed: ${result.error}`,
          errorCode: result.status,
          lastExtraction: null,
          closing: false,
          closeError: null,
        });
        return;
      }

      storeIncidentId(result.data.incident_id);
      await fetchIncidentData(credentials, result.data.incident_id);
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setState((prev) => ({
        ...prev,
        status: 'unavailable',
        error: message,
        errorCode: 0,
      }));
    }
  }, [fetchIncidentData]);

  // ---- Load existing incident ----
  // An optional override (e.g. /incident?id=...) loads a specific past
  // incident from History and adopts it as the current incident.
  const loadIncident = useCallback(async () => {
    let incidentId = overrideIncidentId ?? getStoredIncidentId();
    if (overrideIncidentId) {
      storeIncidentId(overrideIncidentId);
    }
    if (!incidentId) {
      setState((prev) => ({ ...prev, status: 'idle', error: null }));
      return;
    }

    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    try {
      const credResult = await ensureDeviceIdentity();
      if (!mountedRef.current) return;

      if (!credResult.ok) {
        setState({
          status: 'error',
          credentials: null,
          incident: null,
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
          lastExtraction: null,
          closing: false,
          closeError: null,
        });
        return;
      }

      await fetchIncidentData(credResult.data, incidentId);
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setState((prev) => ({
        ...prev,
        status: 'unavailable',
        error: message,
        errorCode: 0,
      }));
    }
  }, [fetchIncidentData, overrideIncidentId]);

  // ---- Submit transcript ----
  const submitTranscript = useCallback(async (
    text: string,
    source: TranscriptSource = 'USER_TYPED',
  ) => {
    const incidentId = getStoredIncidentId();
    if (!incidentId || !state.credentials) {
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: 'No active incident. Start an incident first.',
        errorCode: null,
      }));
      return;
    }

    setState((prev) => ({ ...prev, status: 'submitting', error: null }));

    try {
      const result = await addIncidentTranscript(
        state.credentials,
        incidentId,
        { text, source, batch_id: batchIdForText(text) },
      );

      if (!mountedRef.current) return;

      if (!result.ok) {
        setState((prev) => ({
          ...prev,
          status: 'active',
          error: `Transcript submission failed: ${result.error}`,
          errorCode: result.status,
        }));
        return;
      }

      // Store the extraction result for immediate display
      const extraction = result.data.extraction;

      // Refresh full incident data
      await fetchIncidentData(state.credentials, incidentId);

      // Update with extraction result
      if (mountedRef.current) {
        setState((prev) => ({
          ...prev,
          lastExtraction: extraction,
        }));
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setState((prev) => ({
        ...prev,
        status: 'active',
        error: message,
        errorCode: 0,
      }));
    }
  }, [state.credentials, fetchIncidentData]);

  // ---- Record user action ----
  const confirmAction = useCallback(async (
    actionType: string,
    description: string,
  ) => {
    const incidentId = getStoredIncidentId();
    if (!incidentId || !state.credentials) return;

    try {
      const result = await recordIncidentAction(
        state.credentials,
        incidentId,
        { action_type: actionType, description },
      );

      if (!mountedRef.current) return;

      if (result.ok) {
        await fetchIncidentData(state.credentials, incidentId);
      }
    } catch {
      // Best-effort; don't break the UI
    }
  }, [state.credentials, fetchIncidentData]);

  // ---- Refresh ----
  const refresh = useCallback(async () => {
    const incidentId = getStoredIncidentId();
    if (!incidentId || !state.credentials) return;
    await fetchIncidentData(state.credentials, incidentId);
  }, [state.credentials, fetchIncidentData]);

  // ---- End incident ----
  // Server-side close: the incident is archived via the real close endpoint.
  // Local state (and the stored incident id) are only cleared AFTER the server
  // confirms the closure succeeded. On failure the id is kept so the user can
  // retry, and the error is surfaced without losing the incident.
  const endIncident = useCallback(async () => {
    const incidentId = getStoredIncidentId();
    if (!incidentId || !state.credentials) return;
    if (state.closing) return;

    setState((prev) => ({ ...prev, closing: true, closeError: null }));

    try {
      const result = await closeIncident(state.credentials, incidentId, {});
      if (!mountedRef.current) return;

      if (!result.ok) {
        // Keep the incident id and evidence; surface the error so the close
        // can be retried. Do NOT clear local state on failure.
        setState((prev) => ({
          ...prev,
          closing: false,
          closeError: `Could not close incident: ${result.error}`,
        }));
        return;
      }

      clearStoredIncidentId();
      setState({
        status: 'idle',
        credentials: state.credentials,
        incident: null,
        error: null,
        errorCode: null,
        lastExtraction: null,
        closing: false,
        closeError: null,
      });
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setState((prev) => ({
        ...prev,
        closing: false,
        closeError: `Could not close incident: ${message}`,
      }));
    }
  }, [state.credentials, state.closing]);

  // ---- Clear last extraction ----
  const clearLastExtraction = useCallback(() => {
    setState((prev) => ({ ...prev, lastExtraction: null }));
  }, []);

  // ---- Initialize ----
  useEffect(() => {
    mountedRef.current = true;
    loadIncident();
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, [loadIncident]);

  // ---- Polling ----
  useEffect(() => {
    if (state.status !== 'active' && state.status !== 'submitting') return;
    const interval = setInterval(() => {
      if (mountedRef.current) refresh();
    }, pollIntervalMs);
    return () => clearInterval(interval);
  }, [state.status, refresh, pollIntervalMs]);

  return {
    ...state,
    startNewIncident,
    submitTranscript,
    confirmAction,
    refresh,
    endIncident,
    clearLastExtraction,
  };
}
