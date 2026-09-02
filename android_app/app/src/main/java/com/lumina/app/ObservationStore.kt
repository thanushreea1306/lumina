package com.lumina.app

/**
 * Interface for observation storage operations.
 * Separated from [LocalEventStore] so test doubles can be created
 * without an Android Context.
 */
interface ObservationStore {
    fun saveObservation(observation: PendingObservation)
    fun updateObservation(observation: PendingObservation)
    fun getObservations(sessionId: String): List<PendingObservation>
    fun getPendingObservations(): List<PendingObservation>
    fun getObservation(observationId: String): PendingObservation?
}
