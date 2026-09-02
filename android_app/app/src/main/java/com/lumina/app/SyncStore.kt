package com.lumina.app

import org.json.JSONObject

/**
 * Interface for the store operations that [SyncManager] depends on.
 * Separated from [LocalEventStore] so test doubles can be created
 * without an Android Context.
 */
interface SyncStore {
    fun hasConsent(): Boolean
    fun getSessionId(): String?
    fun setSessionId(sessionId: String?)
    fun getPendingEventIds(): List<String>
    fun getEvent(eventId: String): JSONObject?
    fun markUploaded(eventId: String)
}
