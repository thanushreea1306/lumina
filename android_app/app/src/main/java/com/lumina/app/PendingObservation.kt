package com.lumina.app

import org.json.JSONObject

/**
 * A user-reported observation stored locally before backend sync.
 *
 * Observations are created only when the user explicitly selects a type.
 * They are never inferred from device signals.
 *
 * Sync states:
 *  - [SyncState.PENDING]: created locally, not yet sent to backend
 *  - [SyncState.SENT]: uploaded to backend, awaiting confirmation
 *  - [SyncState.SYNCED]: backend confirmed receipt (HTTP 2xx)
 *  - [SyncState.FAILED]: upload failed; will retry
 */
data class PendingObservation(
    val observationId: String,
    val sessionId: String,
    val observationType: UserObservationType,
    val notes: String?,
    val timestamp: Long,
    val syncState: SyncState = SyncState.PENDING,
    val backendEvidenceId: String? = null,
    val errorMessage: String? = null,
)

enum class SyncState(val label: String) {
    PENDING("Saved locally"),
    SENT("Uploading..."),
    SYNCED("Synced"),
    FAILED("Upload failed"),
}

/**
 * Serialize a [PendingObservation] to JSON for SharedPreferences storage.
 */
fun PendingObservation.toJson(): JSONObject = JSONObject().apply {
    put("observation_id", observationId)
    put("session_id", sessionId)
    put("observation_type", observationType.name)
    put("notes", notes ?: JSONObject.NULL)
    put("timestamp", timestamp)
    put("sync_state", syncState.name)
    put("backend_evidence_id", backendEvidenceId ?: JSONObject.NULL)
    put("error_message", errorMessage ?: JSONObject.NULL)
}

/**
 * Deserialize a [PendingObservation] from JSON.
 */
fun observationFromJson(json: JSONObject): PendingObservation = PendingObservation(
    observationId = json.getString("observation_id"),
    sessionId = json.getString("session_id"),
    observationType = try {
        UserObservationType.valueOf(json.getString("observation_type"))
    } catch (_: IllegalArgumentException) {
        UserObservationType.URGENCY // fallback; should not happen
    },
    notes = if (json.isNull("notes")) null else json.getString("notes"),
    timestamp = json.getLong("timestamp"),
    syncState = try {
        SyncState.valueOf(json.getString("sync_state"))
    } catch (_: IllegalArgumentException) {
        SyncState.PENDING
    },
    backendEvidenceId = if (json.isNull("backend_evidence_id")) null else json.getString("backend_evidence_id"),
    errorMessage = if (json.isNull("error_message")) null else json.getString("error_message"),
)
