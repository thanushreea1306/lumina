/* ============================================================
   LUMINA Incident List Hook
   ============================================================
   Loads the incident history for the History screen.
   No fake data. Real backend is the source of truth.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ensureDeviceIdentity } from '@/lib/api/device';
import { listIncidents } from '@/lib/api/incidents';
import type { DeviceCredentials } from '@/lib/api/device';
import type { IncidentSummary } from '@/types/incident';

// ---- State Types ----

export type IncidentListStatus =
  | 'loading'
  | 'ready'
  | 'error'
  | 'unauthorized'
  | 'unavailable';

export interface IncidentListState {
  status: IncidentListStatus;
  credentials: DeviceCredentials | null;
  incidents: IncidentSummary[];
  error: string | null;
  errorCode: number | null;
}

// ---- Hook ----

export function useIncidentList(limit = 50) {
  const [state, setState] = useState<IncidentListState>({
    status: 'loading',
    credentials: null,
    incidents: [],
    error: null,
    errorCode: null,
  });

  const mountedRef = useRef(true);

  const fetchListData = useCallback(async () => {
    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    try {
      // Step 1: Ensure device identity
      const credResult = await ensureDeviceIdentity();
      if (!mountedRef.current) return;

      if (!credResult.ok) {
        setState((prev) => ({
          ...prev,
          status: 'error',
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
        }));
        return;
      }

      const credentials = credResult.data;

      // Step 2: Fetch incident history
      const result = await listIncidents(credentials, limit);
      if (!mountedRef.current) return;

      if (result.ok) {
        setState({
          status: 'ready',
          credentials,
          incidents: result.data.incidents,
          error: null,
          errorCode: null,
        });
        return;
      }

      if (result.status === 401) {
        setState((prev) => ({
          ...prev,
          status: 'unauthorized',
          error: result.error,
          errorCode: result.status,
        }));
        return;
      }

      if (result.status === 0) {
        setState((prev) => ({
          ...prev,
          status: 'unavailable',
          error: result.error,
          errorCode: 0,
        }));
        return;
      }

      setState((prev) => ({
        ...prev,
        status: 'error',
        error: result.error,
        errorCode: result.status,
      }));
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
  }, [limit]);

  // Initial load
  useEffect(() => {
    mountedRef.current = true;
    fetchListData();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchListData]);

  const refresh = useCallback(() => {
    fetchListData();
  }, [fetchListData]);

  return { ...state, refresh };
}