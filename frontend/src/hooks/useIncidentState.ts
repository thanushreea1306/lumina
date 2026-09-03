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
} from '@/lib/api/incidents';
import type { DeviceCredentials } from '@/lib/api/device';
import type {
  Incident,
  IncidentStatus,
  Priority,
  ExtractionResult,
  TranscriptSource,
} from '@/types/incident';

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
}

// ---- Incident ID persistence (sessionStorage) ----
const INCIDENT_STORAGE_KEY = 'lumina_current_incident_id';

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

export function useIncidentState(pollIntervalMs = 30_000) {
  const [state, setState] = useState<IncidentState>({
    status: 'idle',
    credentials: null,
    incident: null,
    error: null,
    errorCode: null,
    lastExtraction: null,
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
  const loadIncident = useCallback(async () => {
    const incidentId = getStoredIncidentId();
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
  }, [fetchIncidentData]);

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
        { text, source },
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
  const endIncident = useCallback(() => {
    clearStoredIncidentId();
    setState({
      status: 'idle',
      credentials: state.credentials,
      incident: null,
      error: null,
      errorCode: null,
      lastExtraction: null,
    });
  }, [state.credentials]);

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
