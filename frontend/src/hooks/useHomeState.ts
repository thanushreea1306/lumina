/* ============================================================
   LUMINA Home State Hook
   ============================================================
   Manages the Home screen's real-time state: device identity,
   active session detection, decision retrieval, and error
   handling. No fake data. Real backend is the source of truth.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ensureDeviceIdentity } from '@/lib/api/device';
import { getSession, getDecision } from '@/lib/api/sessions';
import type { DeviceCredentials } from '@/lib/api/device';
import type { SafetyState } from '@/types/safety';

// ---- Home State Types ----

export type HomeStatus =
  | 'loading'          // Initial load / fetching
  | 'no_session'       // No active session — calm state
  | 'active_session'   // Active session with decision
  | 'error'            // Backend error or network failure
  | 'unavailable';     // Backend not reachable

export interface HomeSessionData {
  sessionId: string;
  startedAt: string;
  eventCount: number;
  evidenceCount: number;
}

export interface HomeDecisionData {
  state: SafetyState;
  stateLabel: string;
  reasonCodes: string[];
  recommendedAction: string;
  evidenceCount: number;
  missingInformation: string[];
  hasRequestedHighRiskAction: boolean;
  hasPerformedHighRiskAction: boolean;
  observations: string[];
}

export interface HomeState {
  status: HomeStatus;
  credentials: DeviceCredentials | null;
  session: HomeSessionData | null;
  decision: HomeDecisionData | null;
  error: string | null;
  errorCode: number | null;
}

// ---- Store current session ID in sessionStorage (not localStorage) ----
// Session-scoped: clears when the browser tab closes.
const SESSION_STORAGE_KEY = 'lumina_current_session_id';

function getStoredSessionId(): string | null {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeSessionId(sessionId: string): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } catch {
    // Silently fail
  }
}

// ---- Hook ----

export function useHomeState(pollIntervalMs = 30_000) {
  const [state, setState] = useState<HomeState>({
    status: 'loading',
    credentials: null,
    session: null,
    decision: null,
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
          session: null,
          decision: null,
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
        });
        return;
      }

      const credentials = credResult.data;

      // Step 2: Check for stored session ID
      const sessionId = getStoredSessionId();

      if (!sessionId) {
        // No active session — this is the calm "nothing requires attention" state
        if (!controller.signal.aborted) {
          setState({
            status: 'no_session',
            credentials,
            session: null,
            decision: null,
            error: null,
            errorCode: null,
          });
        }
        return;
      }

      // Step 3: Fetch session data
      const sessionResult = await getSession(credentials, sessionId);
      if (!mountedRef.current || controller.signal.aborted) return;

      if (!sessionResult.ok) {
        // Session not found or auth failed — clear the stale session ID
        if (sessionResult.status === 404 || sessionResult.status === 401) {
          try { sessionStorage.removeItem(SESSION_STORAGE_KEY); } catch { /* noop */ }
          setState({
            status: 'no_session',
            credentials,
            session: null,
            decision: null,
            error: null,
            errorCode: null,
          });
          return;
        }

        setState({
          status: 'error',
          credentials,
          session: null,
          decision: null,
          error: sessionResult.error,
          errorCode: sessionResult.status,
        });
        return;
      }

      const sessionData: HomeSessionData = {
        sessionId: sessionResult.data.session_id,
        startedAt: sessionResult.data.started_at,
        eventCount: sessionResult.data.events.length,
        evidenceCount: sessionResult.data.evidence.length,
      };

      // Step 4: Fetch decision
      const decisionResult = await getDecision(credentials, sessionId);
      if (!mountedRef.current || controller.signal.aborted) return;

      if (!decisionResult.ok) {
        // Decision failed but session exists — show session without decision
        setState({
          status: 'active_session',
          credentials,
          session: sessionData,
          decision: null,
          error: `Decision unavailable: ${decisionResult.error}`,
          errorCode: decisionResult.status,
        });
        return;
      }

      const decisionData: HomeDecisionData = {
        state: decisionResult.data.decision.state as SafetyState,
        stateLabel: decisionResult.data.decision.state_label,
        reasonCodes: decisionResult.data.decision.reason_codes,
        recommendedAction: decisionResult.data.decision.recommended_action,
        evidenceCount: decisionResult.data.context.evidence_count,
        missingInformation: decisionResult.data.decision.missing_information,
        hasRequestedHighRiskAction: decisionResult.data.context.has_requested_high_risk_action,
        hasPerformedHighRiskAction: decisionResult.data.context.has_performed_high_risk_action,
        observations: decisionResult.data.context.observations,
      };

      if (!controller.signal.aborted) {
        setState({
          status: 'active_session',
          credentials,
          session: sessionData,
          decision: decisionData,
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

  const startSession = useCallback((sessionId: string) => {
    storeSessionId(sessionId);
    fetchHomeData();
  }, [fetchHomeData]);

  return { ...state, refresh, startSession };
}
