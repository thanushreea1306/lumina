package com.lumina.app

/**
 * Interface for incident-id persistence. Keeps audio uploads bound to the
 * incident LUMINA created on this device so a legitimate upload has an owned
 * target and never needs to guess an id.
 *
 * Separated from [LocalEventStore] so test doubles can be created without an
 * Android Context (same pattern as [SyncStore] and [ObservationStore]).
 */
interface IncidentStore {
    fun getIncidentId(): String?
    fun setIncidentId(incidentId: String?)
}