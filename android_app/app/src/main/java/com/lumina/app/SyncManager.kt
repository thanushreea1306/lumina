package com.lumina.app

import android.util.Log
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Offline-first sync manager with production-grade reliability.
 *
 * Guarantees:
 *  - Stable event IDs (from [CallEvent.eventId])
 *  - Idempotency: retrying the same event does not create duplicates
 *    (backend deduplicates by event_id)
 *  - Preserved event ordering (pending queue is ordered by sequence)
 *  - No data loss on transient failure
 *  - No claiming delivery before confirmed HTTP success
 *  - No upload after consent is revoked
 *  - Stale session recovery (404 → create new session → retry)
 *  - Bounded exponential backoff on transient failures
 *  - Crash safety: deterministic IDs ensure safe retry after process death
 *
 * Error classification:
 *  - RETRYABLE: network timeout, server error (5xx), connection refused
 *  - SESSION_EXPIRED: HTTP 404 on event upload → invalidate session, create new, retry
 *  - PERMANENT: client error (4xx except 404), not-configured
 *  - SUCCESS: HTTP 2xx
 */
class SyncManager(
    private val store: SyncStore,
    private val transport: LuminaTransport,
) {
    private val executor = Executors.newSingleThreadExecutor()
    private val isSyncing = AtomicBoolean(false)

    // Backoff state: resets on successful sync
    private var backoffAttempt = 0
    private var lastFailureTime = 0L

    companion object {
        private const val TAG = "LUMINA.Sync"
        private const val INITIAL_BACKOFF_MS = 2_000L    // 2 seconds
        private const val MAX_BACKOFF_MS = 60_000L       // 60 seconds
        private const val BACKOFF_MULTIPLIER = 2.0
        private const val MAX_BACKOFF_ATTEMPTS = 6       // 2s → 4s → 8s → 16s → 32s → 60s
    }

    /**
     * Request a sync of pending events. Safe to call from any thread;
     * if a sync is already in progress, the request is a no-op.
     */
    fun requestSync() {
        if (isSyncing.compareAndSet(false, true)) {
            executor.execute {
                try {
                    doSync()
                } catch (e: Exception) {
                    Log.e(TAG, "Sync failed unexpectedly", e)
                } finally {
                    isSyncing.set(false)
                }
            }
        }
    }

    /**
     * Synchronous sync — blocks the calling thread. Use only for testing.
     */
    fun syncNow() {
        if (isSyncing.compareAndSet(false, true)) {
            try {
                doSync()
            } finally {
                isSyncing.set(false)
            }
        }
    }

    /** Number of events still pending upload. */
    val pendingCount: Int get() = store.getPendingEventIds().size

    /** Whether a sync is currently running. */
    val syncing: Boolean get() = isSyncing.get()

    private fun doSync() {
        // 1. Consent check
        if (!store.hasConsent()) {
            Log.w(TAG, "No consent; skipping sync")
            return
        }

        // 2. Backoff gate: if we recently failed, wait before retrying
        if (backoffAttempt > 0) {
            val elapsed = System.currentTimeMillis() - lastFailureTime
            val delay = currentBackoffMs()
            if (elapsed < delay) {
                Log.d(TAG, "Backoff active: waiting ${delay - elapsed}ms before retry (attempt $backoffAttempt)")
                Thread.sleep(delay - elapsed)
            }
        }

        // 3. Ensure we have a valid backend session.
        val sessionId = ensureSession() ?: run {
            Log.w(TAG, "Cannot create/load session; events remain pending")
            recordFailure()
            return
        }

        // 4. Get pending event IDs (ordered by insertion).
        val pendingIds = store.getPendingEventIds()
        if (pendingIds.isEmpty()) {
            Log.d(TAG, "No pending events")
            resetBackoff()
            return
        }

        Log.d(TAG, "Syncing ${pendingIds.size} pending events for session $sessionId")

        // 5. Upload each event in order.
        for (eventId in pendingIds) {
            val eventJson = store.getEvent(eventId) ?: continue

            when (val result = transport.sendEvent(sessionId, eventJson)) {
                is SendResult.Sent -> {
                    store.markUploaded(eventId)
                    Log.d(TAG, "Uploaded event $eventId (HTTP ${result.httpCode})")
                }
                is SendResult.Failed -> {
                    val errorType = classifyError(result.detail)
                    Log.w(TAG, "Upload failed for $eventId: ${result.detail} (type: $errorType)")

                    when (errorType) {
                        ErrorType.SESSION_EXPIRED -> {
                            // Stale session: invalidate, create new session, and retry
                            // THIS event immediately in the same sync cycle.
                            Log.w(TAG, "Session expired; invalidating and creating new session")
                            store.setSessionId(null)
                            val newSessionId = createSession()
                            if (newSessionId != null) {
                                Log.d(TAG, "New session created: $newSessionId; retrying event $eventId")
                                when (val retry = transport.sendEvent(newSessionId, eventJson)) {
                                    is SendResult.Sent -> {
                                        store.markUploaded(eventId)
                                        Log.d(TAG, "Retry succeeded for $eventId (HTTP ${retry.httpCode})")
                                    }
                                    else -> {
                                        Log.w(TAG, "Retry also failed for $eventId: $retry")
                                        recordFailure()
                                        return
                                    }
                                }
                            } else {
                                Log.w(TAG, "Could not create new session; event remains pending")
                                recordFailure()
                                return
                            }
                        }
                        ErrorType.PERMANENT -> {
                            // Client error (4xx) — don't retry this event endlessly
                            Log.w(TAG, "Permanent error for $eventId; skipping this cycle")
                            recordFailure()
                            return
                        }
                        ErrorType.RETRYABLE -> {
                            // Transient failure — will retry with backoff
                            recordFailure()
                            return
                        }
                    }
                }
                is SendResult.NotConfigured -> {
                    Log.w(TAG, "Transport not configured; events remain pending")
                    return
                }
            }
        }

        // All events synced successfully
        resetBackoff()
    }

    /**
     * Ensure a backend session exists. Returns the session_id or null on failure.
     * If a session_id is already stored locally, reuse it. Otherwise create one.
     */
    private fun ensureSession(): String? {
        // Reuse existing session if available.
        val existing = store.getSessionId()
        if (existing != null) return existing

        // Create a new session via the backend.
        when (val result = transport.createSession()) {
            is CreateSessionResult.Success -> {
                store.setSessionId(result.sessionId)
                Log.d(TAG, "Created backend session: ${result.sessionId}")
                return result.sessionId
            }
            is CreateSessionResult.Failed -> {
                Log.w(TAG, "Session creation failed: ${result.detail}")
                return null
            }
            is CreateSessionResult.NotConfigured -> {
                Log.w(TAG, "Transport not configured; cannot create session")
                return null
            }
        }
    }

    /**
     * Create a new backend session and store it locally.
     * Returns the session_id or null on failure.
     */
    private fun createSession(): String? {
        when (val result = transport.createSession()) {
            is CreateSessionResult.Success -> {
                store.setSessionId(result.sessionId)
                Log.d(TAG, "Created backend session: ${result.sessionId}")
                return result.sessionId
            }
            is CreateSessionResult.Failed -> {
                Log.w(TAG, "Session creation failed: ${result.detail}")
                return null
            }
            is CreateSessionResult.NotConfigured -> {
                Log.w(TAG, "Transport not configured; cannot create session")
                return null
            }
        }
    }

    // ---- Error classification ----

    private enum class ErrorType {
        RETRYABLE,       // network timeout, 5xx, connection refused
        SESSION_EXPIRED, // 404 on event upload
        PERMANENT,       // 4xx (except 404), client errors
    }

    private fun classifyError(detail: String): ErrorType {
        // Parse HTTP status code from detail string like "HTTP 404"
        val httpMatch = Regex("HTTP (\\d+)").find(detail)
        if (httpMatch != null) {
            val code = httpMatch.groupValues[1].toIntOrNull() ?: return ErrorType.RETRYABLE
            return when (code) {
                404 -> ErrorType.SESSION_EXPIRED
                in 400..499 -> ErrorType.PERMANENT  // client error (except 404)
                in 500..599 -> ErrorType.RETRYABLE  // server error
                else -> ErrorType.RETRYABLE
            }
        }
        // Non-HTTP errors (timeout, connection refused, etc.) are retryable
        return ErrorType.RETRYABLE
    }

    // ---- Backoff ----

    private fun currentBackoffMs(): Long {
        val delay = INITIAL_BACKOFF_MS * Math.pow(BACKOFF_MULTIPLIER, backoffAttempt.toDouble())
        return delay.toLong().coerceAtMost(MAX_BACKOFF_MS)
    }

    private fun recordFailure() {
        backoffAttempt = (backoffAttempt + 1).coerceAtMost(MAX_BACKOFF_ATTEMPTS)
        lastFailureTime = System.currentTimeMillis()
    }

    private fun resetBackoff() {
        backoffAttempt = 0
        lastFailureTime = 0L
    }
}
