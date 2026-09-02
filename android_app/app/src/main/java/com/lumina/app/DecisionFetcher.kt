package com.lumina.app

import android.util.Log
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference

/**
 * Fetches safety decisions from the backend and exposes them for UI display.
 *
 * The backend is the single source of truth for safety decisions.
 * Android never computes, infers, or fabricates a decision locally.
 *
 * Decision lifecycle:
 *  1. User creates observations → synced to backend
 *  2. [fetchDecision] called → GET /api/sessions/{id}/decision
 *  3. Backend evaluates evidence + observations → deterministic SafetyState
 *  4. Decision displayed to user with honest language
 *
 * If the backend is unreachable, the decision is null and the UI must
 * show "Decision unavailable" — never a fake safe/danger result.
 */
class DecisionFetcher(
    private val transport: LuminaTransport,
) {
    private val executor = Executors.newSingleThreadExecutor()
    private val _currentDecision = AtomicReference<DecisionResult?>(null)

    companion object {
        private const val TAG = "LUMINA.Decision"
    }

    /** The most recently fetched decision, or null if none received yet. */
    val currentDecision: DecisionResult? get() = _currentDecision.get()

    /**
     * Fetch the decision from the backend. Runs on a background thread.
     * Calls [onResult] on the calling thread with the result.
     */
    fun fetchDecision(sessionId: String, onResult: (DecisionResult) -> Unit) {
        executor.execute {
            val result = doFetch(sessionId)
            _currentDecision.set(result)
            onResult(result)
        }
    }

    /**
     * Synchronous fetch for testing.
     */
    fun fetchNow(sessionId: String): DecisionResult {
        val result = doFetch(sessionId)
        _currentDecision.set(result)
        return result
    }

    private fun doFetch(sessionId: String): DecisionResult {
        return when (val result = transport.getDecision(sessionId)) {
            is DecisionFetchResult.Success -> {
                DecisionResult.Available(result.decisionJson)
            }
            is DecisionFetchResult.Failed -> {
                Log.w(TAG, "Decision fetch failed: ${result.detail}")
                DecisionResult.Unavailable(result.detail)
            }
            is DecisionFetchResult.NotConfigured -> {
                DecisionResult.Unavailable("Backend not configured")
            }
        }
    }
}

/**
 * Represents the state of a fetched decision.
 */
sealed class DecisionResult {
    /** Decision received from backend. The JSON contains the full decision. */
    data class Available(val decisionJson: JSONObject) : DecisionResult()

    /** Decision could not be retrieved. [reason] explains why. */
    data class Unavailable(val reason: String) : DecisionResult()
}
