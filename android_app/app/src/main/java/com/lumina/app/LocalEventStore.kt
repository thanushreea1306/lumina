package com.lumina.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Device-local store for observed call events and sync state.
 *
 * Phase 2: persisted call events locally (SharedPreferences).
 * Phase 4A: adds session_id persistence, pending-upload queue, and
 * uploaded-event tracking for offline-first sync.
 *
 * Events live on-device until uploaded via [SyncManager]. If the backend
 * is unreachable, events remain pending — nothing is lost, nothing is
 * fabricated.
 */
class LocalEventStore(context: Context) : SyncStore, ObservationStore {

    private val prefs =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    // ---- Event storage (unchanged from Phase 2) ----

    /** Returns the current number of locally recorded events (honest counter). */
    fun count(): Int {
        val raw = prefs.getString(KEY_COUNTER, null) ?: return 0
        return raw.toIntOrNull() ?: 0
    }

    /** Persist one event. Returns the new count. */
    fun append(event: CallEvent): Int {
        val n = count() + 1
        prefs.edit()
            .putString("event_$n", event.toJson().toString())
            .putString(KEY_COUNTER, n.toString())
            .apply()
        // Add to pending queue (idempotent — set semantics).
        addToPending(event.eventId)
        return n
    }

    /** Drop all locally recorded events and reset the counter. */
    fun clear() {
        prefs.edit().clear().apply()
    }

    // ---- Session ID ----

    /** Returns the stored backend session ID, or null if none exists. */
    override fun getSessionId(): String? {
        return prefs.getString(KEY_SESSION_ID, null)
    }

    /** Store the backend session ID. */
    override fun setSessionId(sessionId: String?) {
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply()
    }

    // ---- Consent ----

    /** Whether the user has consented to monitoring and upload. */
    override fun hasConsent(): Boolean {
        return prefs.getBoolean(KEY_CONSENTED, false)
    }

    /** Store consent state. */
    fun setConsent(consented: Boolean) {
        prefs.edit().putBoolean(KEY_CONSENTED, consented).apply()
    }

    // ---- Pending / uploaded tracking ----

    /** Get all event IDs that have not yet been uploaded (ordered by insertion). */
    override fun getPendingEventIds(): List<String> {
        val raw = prefs.getString(KEY_PENDING_IDS, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).map { arr.getString(it) }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /** Mark an event as successfully uploaded. Removes from pending. */
    override fun markUploaded(eventId: String) {
        val pending = getPendingEventIds().toMutableList()
        pending.remove(eventId)
        savePendingIds(pending)
    }

    /** Get a stored event by its event ID, or null if not found. */
    override fun getEvent(eventId: String): JSONObject? {
        val counter = count()
        for (i in 1..counter) {
            val raw = prefs.getString("event_$i", null) ?: continue
            try {
                val json = JSONObject(raw)
                if (json.optString("event_id") == eventId) return json
            } catch (_: Exception) {
                // Skip malformed entries.
            }
        }
        return null
    }

    // ---- Private helpers ----

    private fun addToPending(eventId: String) {
        val pending = getPendingEventIds().toMutableList()
        if (!pending.contains(eventId)) {
            pending.add(eventId)
            savePendingIds(pending)
        }
    }

    private fun savePendingIds(ids: List<String>) {
        val arr = JSONArray()
        ids.forEach { arr.put(it) }
        prefs.edit().putString(KEY_PENDING_IDS, arr.toString()).apply()
    }

    // ---- Observation storage (Phase 4B) ----

    override fun saveObservation(observation: PendingObservation) {
        val existing = getObservationsRaw().toMutableList()
        existing.add(observation)
        saveObservationsRaw(existing)
    }

    override fun updateObservation(observation: PendingObservation) {
        val existing = getObservationsRaw().toMutableList()
        val idx = existing.indexOfFirst { it.observationId == observation.observationId }
        if (idx >= 0) {
            existing[idx] = observation
            saveObservationsRaw(existing)
        }
    }

    override fun getObservations(sessionId: String): List<PendingObservation> {
        return getObservationsRaw().filter { it.sessionId == sessionId }
    }

    override fun getPendingObservations(): List<PendingObservation> {
        return getObservationsRaw().filter {
            it.syncState == SyncState.PENDING || it.syncState == SyncState.FAILED
        }
    }

    override fun getObservation(observationId: String): PendingObservation? {
        return getObservationsRaw().find { it.observationId == observationId }
    }

    private fun getObservationsRaw(): List<PendingObservation> {
        val raw = prefs.getString(KEY_OBSERVATIONS, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).map { observationFromJson(arr.getJSONObject(it)) }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun saveObservationsRaw(observations: List<PendingObservation>) {
        val arr = JSONArray()
        observations.forEach { arr.put(it.toJson()) }
        prefs.edit().putString(KEY_OBSERVATIONS, arr.toString()).apply()
    }

    private companion object {
        const val PREFS_NAME = "lumina_local_events"
        const val KEY_COUNTER = "event_count"
        const val KEY_SESSION_ID = "backend_session_id"
        const val KEY_CONSENTED = "user_consented"
        const val KEY_PENDING_IDS = "pending_event_ids"
        const val KEY_OBSERVATIONS = "pending_observations"
    }
}
