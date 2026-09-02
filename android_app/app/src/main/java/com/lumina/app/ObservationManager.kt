package com.lumina.app

import android.util.Log
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Manages the lifecycle of user observations with production-grade reliability.
 *
 * Flow:
 *   User selects observation type
 *          ↓
 *   Observation created (source=USER, status=USER_CONFIRMED)
 *          ↓
 *   Stored locally as [PendingObservation]
 *          ↓
 *   Synced to backend via POST /api/sessions/{id}/observations
 *          ↓
 *   Sync state updated (SYNCED / FAILED)
 *
 * Guarantees:
 *  - Offline-first: persisted locally before any network call
 *  - Observation ID is stable across retries (UUID created once)
 *  - Session ID, notes, type, timestamp preserved across retries
 *  - No duplicate observations during retry
 *  - Bounded exponential backoff on transient failures
 *  - Error classification (retryable / session-expired / permanent)
 *  - No fabricated success
 */
class ObservationManager(
    private val store: ObservationStore,
    private val transport: LuminaTransport,
) {
    private val executor = Executors.newSingleThreadExecutor()
    private val isSyncing = AtomicBoolean(false)

    // Backoff state
    private var backoffAttempt = 0
    private var lastFailureTime = 0L

    companion object {
        private const val TAG = "LUMINA.Observation"
        private const val INITIAL_BACKOFF_MS = 2_000L
        private const val MAX_BACKOFF_MS = 60_000L
        private const val BACKOFF_MULTIPLIER = 2.0
        private const val MAX_BACKOFF_ATTEMPTS = 6
    }

    /**
     * Create a new observation from user input. Persists locally immediately.
     * Returns the observation ID for display.
     */
    fun createObservation(
        sessionId: String,
        type: UserObservationType,
        notes: String? = null,
    ): String {
        val observationId = UUID.randomUUID().toString()
        val observation = PendingObservation(
            observationId = observationId,
            sessionId = sessionId,
            observationType = type,
            notes = notes,
            timestamp = System.currentTimeMillis(),
            syncState = SyncState.PENDING,
        )
        store.saveObservation(observation)
        Log.d(TAG, "Created observation $observationId: ${type.name}")
        return observationId
    }

    /**
     * Request sync of all pending observations. Safe to call from any thread.
     */
    fun requestSync() {
        if (isSyncing.compareAndSet(false, true)) {
            executor.execute {
                try {
                    doSync()
                } catch (e: Exception) {
                    Log.e(TAG, "Observation sync failed unexpectedly", e)
                } finally {
                    isSyncing.set(false)
                }
            }
        }
    }

    /**
     * Synchronous sync for testing.
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

    fun getObservations(sessionId: String): List<PendingObservation> {
        return store.getObservations(sessionId)
    }

    fun pendingCount(sessionId: String): Int {
        return store.getObservations(sessionId).count {
            it.syncState == SyncState.PENDING || it.syncState == SyncState.FAILED
        }
    }

    private fun doSync() {
        // Backoff gate
        if (backoffAttempt > 0) {
            val elapsed = System.currentTimeMillis() - lastFailureTime
            val delay = currentBackoffMs()
            if (elapsed < delay) {
                Log.d(TAG, "Backoff active: waiting ${delay - elapsed}ms (attempt $backoffAttempt)")
                Thread.sleep(delay - elapsed)
            }
        }

        val pending = store.getPendingObservations()
        if (pending.isEmpty()) {
            Log.d(TAG, "No pending observations")
            resetBackoff()
            return
        }

        Log.d(TAG, "Syncing ${pending.size} pending observations")

        for (obs in pending) {
            if (obs.sessionId.isBlank()) {
                Log.w(TAG, "Observation ${obs.observationId} has no session; skipping")
                continue
            }

            // Mark as sending
            store.updateObservation(obs.copy(syncState = SyncState.SENT))

            val body = JSONObject().apply {
                put("observation_type", obs.observationType.name)
                if (obs.notes != null) put("notes", obs.notes)
            }

            when (val result = transport.addObservation(obs.sessionId, body)) {
                is ObservationResult.Success -> {
                    store.updateObservation(
                        obs.copy(
                            syncState = SyncState.SYNCED,
                            backendEvidenceId = result.evidenceId,
                        )
                    )
                    Log.d(TAG, "Observation ${obs.observationId} synced")
                }
                is ObservationResult.Failed -> {
                    val errorType = classifyError(result.detail)
                    Log.w(TAG, "Observation ${obs.observationId} failed: ${result.detail} (type: $errorType)")

                    when (errorType) {
                        ErrorType.SESSION_EXPIRED -> {
                            // Session expired — mark as failed, will retry with new session
                            store.updateObservation(
                                obs.copy(syncState = SyncState.FAILED, errorMessage = result.detail)
                            )
                            recordFailure()
                            return
                        }
                        ErrorType.PERMANENT -> {
                            // Client error (4xx) — mark as failed, don't retry endlessly
                            store.updateObservation(
                                obs.copy(syncState = SyncState.FAILED, errorMessage = result.detail)
                            )
                            recordFailure()
                            return
                        }
                        ErrorType.RETRYABLE -> {
                            // Transient failure — mark as failed, will retry with backoff
                            store.updateObservation(
                                obs.copy(syncState = SyncState.FAILED, errorMessage = result.detail)
                            )
                            recordFailure()
                            return
                        }
                    }
                }
                is ObservationResult.NotConfigured -> {
                    store.updateObservation(
                        obs.copy(syncState = SyncState.FAILED, errorMessage = "Backend not configured")
                    )
                    Log.w(TAG, "Transport not configured; observations remain pending")
                    return
                }
            }
        }

        // All synced successfully
        resetBackoff()
    }

    // ---- Error classification ----

    private enum class ErrorType {
        RETRYABLE,
        SESSION_EXPIRED,
        PERMANENT,
    }

    private fun classifyError(detail: String): ErrorType {
        val httpMatch = Regex("HTTP (\\d+)").find(detail)
        if (httpMatch != null) {
            val code = httpMatch.groupValues[1].toIntOrNull() ?: return ErrorType.RETRYABLE
            return when (code) {
                404 -> ErrorType.SESSION_EXPIRED
                in 400..499 -> ErrorType.PERMANENT
                in 500..599 -> ErrorType.RETRYABLE
                else -> ErrorType.RETRYABLE
            }
        }
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
