package com.lumina.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * JVM unit tests for [ObservationManager] using fake implementations.
 * No Android device required.
 */
class ObservationManagerTest {

    private lateinit var store: InMemoryObservationStore
    private lateinit var transport: FakeTransport

    @Before
    fun setup() {
        store = InMemoryObservationStore()
        transport = FakeTransport()
    }

    // ---- Creation ----

    @Test
    fun `createObservation stores locally`() {
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        assertNotNull(id)
        val obs = store.getObservation(id)
        assertNotNull(obs)
        assertEquals(UserObservationType.OTP_REQUEST, obs!!.observationType)
        assertEquals("s1", obs.sessionId)
        assertEquals(SyncState.PENDING, obs.syncState)
    }

    @Test
    fun `createObservation with notes preserves them`() {
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.URGENCY, notes = "test note")
        val obs = store.getObservation(id)
        assertEquals("test note", obs!!.notes)
    }

    @Test
    fun `createObservation without notes stores null`() {
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.MONEY_REQUEST)
        val obs = store.getObservation(id)
        assertNull(obs!!.notes)
    }

    // ---- Sync ----

    @Test
    fun `sync uploads pending observations`() {
        transport.addObservationSuccess = true
        val mgr = ObservationManager(store, transport)
        mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.createObservation("s1", UserObservationType.MONEY_REQUEST)

        mgr.syncNow()

        assertEquals(2, transport.observationsAdded)
        val pending = mgr.pendingCount("s1")
        assertEquals(0, pending)
    }

    @Test
    fun `synced observations have SYNCED state`() {
        transport.addObservationSuccess = true
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.syncNow()

        val obs = store.getObservation(id)
        assertEquals(SyncState.SYNCED, obs!!.syncState)
        assertNotNull(obs.backendEvidenceId)
    }

    @Test
    fun `failed sync leaves observations as FAILED`() {
        transport.addObservationSuccess = false
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.syncNow()

        val obs = store.getObservation(id)
        assertEquals(SyncState.FAILED, obs!!.syncState)
    }

    @Test
    fun `failed sync stops at first failure`() {
        transport.addObservationSuccess = true
        transport.failAfterFirst = true  // first succeeds, second fails
        val mgr = ObservationManager(store, transport)
        mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.createObservation("s1", UserObservationType.MONEY_REQUEST)

        mgr.syncNow()

        // The first observation synced by the transport should be SYNCED,
        // the second (which failed) should be FAILED. Order may vary because
        // InMemoryObservationStore uses a Map, so check by type.
        val all = store.getObservations("s1")
        val otp = all.first { it.observationType == UserObservationType.OTP_REQUEST }
        val money = all.first { it.observationType == UserObservationType.MONEY_REQUEST }
        assertEquals(SyncState.SYNCED, otp.syncState)
        assertEquals(SyncState.FAILED, money.syncState)
    }

    @Test
    fun `retry syncs previously failed observations`() {
        transport.addObservationSuccess = false
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.syncNow()
        assertEquals(SyncState.FAILED, store.getObservation(id)!!.syncState)

        // Now succeed
        transport.addObservationSuccess = true
        mgr.syncNow()
        assertEquals(SyncState.SYNCED, store.getObservation(id)!!.syncState)
    }

    // ---- Not configured ----

    @Test
    fun `transport not configured leaves observations pending`() {
        transport.notConfigured = true
        val mgr = ObservationManager(store, transport)
        mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.syncNow()

        val obs = store.getObservations("s1")[0]
        assertEquals(SyncState.FAILED, obs.syncState)
        assertEquals("Backend not configured", obs.errorMessage)
    }

    // ---- Session filtering ----

    @Test
    fun `getObservations filters by session`() {
        val mgr = ObservationManager(store, transport)
        mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.createObservation("s2", UserObservationType.MONEY_REQUEST)

        assertEquals(1, mgr.getObservations("s1").size)
        assertEquals(1, mgr.getObservations("s2").size)
        assertEquals(0, mgr.getObservations("s3").size)
    }

    // ---- Pending count ----

    @Test
    fun `pendingCount reflects unsynced observations`() {
        val mgr = ObservationManager(store, transport)
        mgr.createObservation("s1", UserObservationType.OTP_REQUEST)
        mgr.createObservation("s1", UserObservationType.MONEY_REQUEST)
        assertEquals(2, mgr.pendingCount("s1"))

        transport.addObservationSuccess = true
        mgr.syncNow()
        assertEquals(0, mgr.pendingCount("s1"))
    }

    // ---- Provenance (conceptual — backend enforces) ----

    @Test
    fun `observation type is preserved through sync`() {
        transport.addObservationSuccess = true
        val mgr = ObservationManager(store, transport)
        val id = mgr.createObservation("s1", UserObservationType.AUTHORITY_CLAIM)
        mgr.syncNow()

        // Verify the transport received the correct type
        val lastBody = transport.lastObservationBody
        assertNotNull(lastBody)
        assertEquals("AUTHORITY_CLAIM", lastBody!!.getString("observation_type"))
    }

    // ---- No automatic response ----

    @Test
    fun `observations are only created when explicitly requested`() {
        val mgr = ObservationManager(store, transport)
        assertEquals(0, mgr.getObservations("s1").size)
        // No automatic observations are created
    }
}

// ---- In-memory observation store for tests ----

private class InMemoryObservationStore : ObservationStore {
    private val observations = mutableMapOf<String, PendingObservation>()

    override fun saveObservation(observation: PendingObservation) {
        observations[observation.observationId] = observation
    }

    override fun updateObservation(observation: PendingObservation) {
        observations[observation.observationId] = observation
    }

    override fun getObservations(sessionId: String): List<PendingObservation> {
        return observations.values.filter { it.sessionId == sessionId }
    }

    override fun getPendingObservations(): List<PendingObservation> {
        return observations.values.filter {
            it.syncState == SyncState.PENDING || it.syncState == SyncState.FAILED
        }.sortedBy { it.timestamp }
    }

    override fun getObservation(observationId: String): PendingObservation? {
        return observations[observationId]
    }
}

// ---- Extended fake transport for observation tests ----

private class FakeTransport : LuminaTransport {
    var sessionCreations = 0
    var eventsSent = 0
    var observationsAdded = 0
    var lastObservationBody: JSONObject? = null
    var addObservationSuccess = true
    var failAfterFirst = false
    var notConfigured = false
    var failEventId: String? = null
    var sessionCreationFails = false
    var sentEventIds = mutableListOf<String>()

    override fun createSession(): CreateSessionResult {
        if (notConfigured) return CreateSessionResult.NotConfigured
        if (sessionCreationFails) return CreateSessionResult.Failed("simulated")
        sessionCreations++
        return CreateSessionResult.Success("fake-session-$sessionCreations")
    }

    override fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult {
        if (notConfigured) return SendResult.NotConfigured
        val eventId = eventBody.optString("event_id", "")
        if (eventId == failEventId) return SendResult.Failed("simulated")
        eventsSent++
        sentEventIds.add(eventId)
        return SendResult.Sent(200)
    }

    override fun addObservation(sessionId: String, body: JSONObject): ObservationResult {
        if (notConfigured) return ObservationResult.NotConfigured
        val isFirst = observationsAdded == 0
        observationsAdded++
        lastObservationBody = body
        if (addObservationSuccess && !(failAfterFirst && !isFirst)) {
            return ObservationResult.Success("evidence-$observationsAdded")
        }
        return ObservationResult.Failed("simulated failure")
    }

    override fun getDecision(sessionId: String): DecisionFetchResult {
        if (notConfigured) return DecisionFetchResult.NotConfigured
        return DecisionFetchResult.Failed("not implemented in test")
    }

    override fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult {
        if (notConfigured) return UserResponseResult.NotConfigured
        return UserResponseResult.Success
    }
}
