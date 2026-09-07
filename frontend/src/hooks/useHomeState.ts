/* ============================================================
   LUMINA Home State Hook
   ============================================================
   Manages the Home screen's real-time state: device identity,
   active incident detection, recent incident history, and error
   handling. No fake data. Real backend is the source of truth.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ensureDeviceIdentity } from '@/lib/api/device';
import { listIncidents, getIncident } from '@/lib/api/incidents';
import type { DeviceCredentials } from '@/lib/api/device';
import type { Incident, IncidentSummary } from '@/types/incident';

// ---- Home State Types ----

export type HomeStatus =
  | 'loading'          // Initial load / fetching
  | 'ready'            // Ready to show content
  | 'error'            // Backend error or network failure
  | 'unavailable';     // Backend not reachable

export type IncidentListStatus =
  | 'loading'
  | 'ready'
  | 'error'
  | 'unauthorized'
  | 'unavailable';

export interface HomeState {
  status: HomeStatus;
  credentials: DeviceCredentials | null;
  incidents: IncidentSummary[];
  incidentsStatus: IncidentListStatus;
  incidentsError: string | null;
  activeIncident: Incident | null;
  error: string | null;
  errorCode: number | null;
}

// ---- Store current incident ID in sessionStorage (not localStorage) ----
// Session-scoped: clears when the browser tab closes.
const ACTIVE_INCIDENT_KEY = 'lumina_current_incident_id';

function getActiveIncidentId(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_INCIDENT_KEY);
  } catch {
    return null;
  }
}

function clearActiveIncidentId(): void {
  try {
    sessionStorage.removeItem(ACTIVE_INCIDENT_KEY);
  } catch {
    // Silently fail
  }
}

// ---- Hook ----

export function useHomeState(pollIntervalMs = 30_000) {
  const [state, setState] = useState<HomeState>({
    status: 'loading',
    credentials: null,
    incidents: [],
    incidentsStatus: 'loading',
    incidentsError: null,
    activeIncident: null,
    error: null,
    errorCode: null,
  });

  const mountedRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  const fetchHomeData = useCallback(async () => {
    // Cancel any previous in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // Step 1: Ensure device identity
      const credResult = await ensureDeviceIdentity();
      if (!mountedRef.current) return;

      if (!credResult.ok) {
        setState({
          status: 'error',
          credentials: null,
          incidents: [],
          incidentsStatus: 'error',
          incidentsError: null,
          activeIncident: null,
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
        });
        return;
      }

      const credentials = credResult.data;

      // Step 2: Fetch recent incident history
      const listResult = await listIncidents(credentials, 50);
      if (!mountedRef.current || controller.signal.aborted) return;

      let incidents: IncidentSummary[] = [];
      let incidentsStatus: IncidentListStatus = 'ready';
      let incidentsError: string | null = null;

      if (listResult.ok) {
        incidents = listResult.data.incidents;
      } else if (listResult.status === 401) {
        incidentsStatus = 'unauthorized';
      } else if (listResult.status === 0) {
        incidentsStatus = 'unavailable';
        incidentsError = listResult.error;
      } else {
        incidentsStatus = 'error';
        incidentsError = listResult.error;
      }

      // Step 3: Fetch active incident (if one is currently in progress)
      let activeIncident: Incident | null = null;
      const incidentId = getActiveIncidentId();
      if (incidentId) {
        const incidentResult = await getIncident(credentials, incidentId);
        if (!mountedRef.current || controller.signal.aborted) return;
        if (incidentResult.ok) {
          activeIncident = incidentResult.data;
        } else if (incidentResult.status === 404 || incidentResult.status === 401) {
          // Stale stored id — clear it so the front door reads "all clear"
          clearActiveIncidentId();
        }
      }

      if (!controller.signal.aborted) {
        setState({
          status: 'ready',
          credentials,
          incidents,
          incidentsStatus,
          incidentsError,
          activeIncident,
          error: null,
          errorCode: null,
        });
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

  // Initial load + polling
  useEffect(() => {
    mountedRef.current = true;
    fetchHomeData();

    const interval = setInterval(() => {
      if (mountedRef.current) {
        fetchHomeData();
      }
    }, pollIntervalMs);

    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
      clearInterval(interval);
    };
  }, [fetchHomeData, pollIntervalMs]);

  const refresh = useCallback(() => {
    fetchHomeData();
  }, [fetchHomeData]);

  return { ...state, refresh };
}