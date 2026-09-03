/* ============================================================
   LUMINA Session State Hook
   ============================================================
   Manages the Active Session lifecycle: creation, observation
   submission, decision retrieval, response recording, outcome.
   No fake data. Real backend is the source of truth.
   ============================================================ */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ensureDeviceIdentity } from '@/lib/api/device';
import {
  createSession,
  getSession,
  getDecision,
  addObservation,
  appendEvent,
} from '@/lib/api/sessions';
import type { DeviceCredentials } from '@/lib/api/device';
import type { SafetyState } from '@/types/safety';

// ---- Session State Types ----

export type SessionStatus =
  | 'idle'            // No session, ready to create
  | 'creating'        // Creating session
  | 'loading'         // Fetching session data
  | 'active'          // Session active with decision
  | 'submitting'      // Submitting observation
  | 'error'           // Error state
  | 'unavailable';    // Backend unreachable

export interface SessionData {
  sessionId: string;
  startedAt: string;
  events: Array<{
    event_type: string;
    sequence: number;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
  evidence: Array<{
    evidence_id: string;
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

export interface DecisionData {
  state: SafetyState;
  stateLabel: string;
  reasonCodes: string[];
  recommendedAction: string;
  evidenceCount: number;
  missingInformation: string[];
  observations: string[];
  hasRequestedHighRiskAction: boolean;
  hasPerformedHighRiskAction: boolean;
  highRiskActions: Array<{
    action: string;
    status: string;
    description: string;
    urgency: string;
  }>;
}

export interface SessionState {
  status: SessionStatus;
  credentials: DeviceCredentials | null;
  session: SessionData | null;
  decision: DecisionData | null;
  error: string | null;
  errorCode: number | null;
}

// ---- Session ID persistence (sessionStorage) ----
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
  } catch { /* noop */ }
}

function clearStoredSessionId(): void {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch { /* noop */ }
}

// ---- Export for use by other hooks ----
export { getStoredSessionId, storeSessionId, clearStoredSessionId };

// ---- Hook ----

export function useSessionState(pollIntervalMs = 15_000) {
  const [state, setState] = useState<SessionState>({
    status: 'idle',
    credentials: null,
    session: null,
    decision: null,
    error: null,
    errorCode: null,
  });

  const mountedRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  const fetchSessionData = useCallback(async (credentials: DeviceCredentials, sessionId: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const sessionResult = await getSession(credentials, sessionId);
      if (!mountedRef.current || controller.signal.aborted) return;

      if (!sessionResult.ok) {
        if (sessionResult.status === 404 || sessionResult.status === 401) {
          clearStoredSessionId();
          setState({
            status: 'idle',
            credentials,
            session: null,
            decision: null,
            error: null,
            errorCode: null,
          });
          return;
        }
        setState((prev) => ({
          ...prev,
          status: 'error',
          error: sessionResult.error,
          errorCode: sessionResult.status,
        }));
        return;
      }

      const sessionData: SessionData = {
        sessionId: sessionResult.data.session_id,
        startedAt: sessionResult.data.started_at,
        events: sessionResult.data.events,
        evidence: sessionResult.data.evidence,
      };

      // Fetch decision
      const decisionResult = await getDecision(credentials, sessionId);
      if (!mountedRef.current || controller.signal.aborted) return;

      if (!decisionResult.ok) {
        setState({
          status: 'active',
          credentials,
          session: sessionData,
          decision: null,
          error: `Decision unavailable: ${decisionResult.error}`,
          errorCode: decisionResult.status,
        });
        return;
      }

      const ctx = decisionResult.data.context;
      const dec = decisionResult.data.decision;
      const decisionData: DecisionData = {
        state: dec.state as SafetyState,
        stateLabel: dec.state_label,
        reasonCodes: dec.reason_codes,
        recommendedAction: dec.recommended_action,
        evidenceCount: ctx.evidence_count,
        missingInformation: dec.missing_information,
        observations: ctx.observations,
        hasRequestedHighRiskAction: ctx.has_requested_high_risk_action,
        hasPerformedHighRiskAction: ctx.has_performed_high_risk_action,
        highRiskActions: (ctx.high_risk_actions as Array<Record<string, unknown>>).map((a) => ({
          action: String(a.action ?? ''),
          status: String(a.status ?? ''),
          description: String(a.description ?? ''),
          urgency: String(a.urgency ?? ''),
        })),
      };

      if (!controller.signal.aborted) {
        setState({
          status: 'active',
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

  // ---- Create session ----
  const startNewSession = useCallback(async () => {
    setState((prev) => ({ ...prev, status: 'creating', error: null }));

    try {
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
      const result = await createSession(credentials);
      if (!mountedRef.current) return;

      if (!result.ok) {
        setState({
          status: 'error',
          credentials,
          session: null,
          decision: null,
          error: `Session creation failed: ${result.error}`,
          errorCode: result.status,
        });
        return;
      }

      storeSessionId(result.data.session_id);
      await fetchSessionData(credentials, result.data.session_id);
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
  }, [fetchSessionData]);

  // ---- Load existing session ----
  const loadSession = useCallback(async () => {
    const sessionId = getStoredSessionId();
    if (!sessionId) {
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
          session: null,
          decision: null,
          error: `Device registration failed: ${credResult.error}`,
          errorCode: credResult.status,
        });
        return;
      }

      await fetchSessionData(credResult.data, sessionId);
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
  }, [fetchSessionData]);

  // ---- Submit observation ----
  const submitObservation = useCallback(async (
    observationType: string,
    notes?: string,
  ) => {
    const sessionId = getStoredSessionId();
    if (!sessionId || !state.credentials) {
      setState((prev) => ({
        ...prev,
        status: 'error',
        error: 'No active session. Create a session first.',
        errorCode: null,
      }));
      return;
    }

    setState((prev) => ({ ...prev, status: 'submitting', error: null }));

    try {
      const result = await addObservation(state.credentials, sessionId, {
        observation_type: observationType,
        notes,
      });

      if (!mountedRef.current) return;

      if (!result.ok) {
        setState((prev) => ({
          ...prev,
          status: 'active',
          error: `Observation failed: ${result.error}`,
          errorCode: result.status,
        }));
        return;
      }

      // Refresh session data after successful observation
      await fetchSessionData(state.credentials, sessionId);
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
  }, [state.credentials, fetchSessionData]);

  // ---- Submit device event ----
  const submitEvent = useCallback(async (
    eventType: string,
    payload?: Record<string, unknown>,
  ) => {
    const sessionId = getStoredSessionId();
    if (!sessionId || !state.credentials) return;

    try {
      await appendEvent(state.credentials, sessionId, {
        event_type: eventType,
        payload,
      });
    } catch {
      // Events are best-effort; don't break the UI
    }
  }, [state.credentials]);

  // ---- Refresh ----
  const refresh = useCallback(async () => {
    const sessionId = getStoredSessionId();
    if (!sessionId || !state.credentials) return;
    await fetchSessionData(state.credentials, sessionId);
  }, [state.credentials, fetchSessionData]);

  // ---- End session (clear stored ID) ----
  const endSession = useCallback(() => {
    clearStoredSessionId();
    setState({
      status: 'idle',
      credentials: state.credentials,
      session: null,
      decision: null,
      error: null,
      errorCode: null,
    });
  }, [state.credentials]);

  // ---- Initialize: load existing session or go idle ----
  useEffect(() => {
    mountedRef.current = true;
    loadSession();

    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, [loadSession]);

  // ---- Polling for active sessions ----
  useEffect(() => {
    if (state.status !== 'active' && state.status !== 'submitting') return;

    const interval = setInterval(() => {
      if (mountedRef.current) {
        refresh();
      }
    }, pollIntervalMs);

    return () => clearInterval(interval);
  }, [state.status, refresh, pollIntervalMs]);

  return {
    ...state,
    startNewSession,
    submitObservation,
    submitEvent,
    refresh,
    endSession,
  };
}
