package com.lumina.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * JVM unit tests for [SyncManager] logic using fake implementations.
 *
 * These verify: offline queue behaviour, retry on failure, idempotency,
 * event ordering, consent blocking, and session creation/reuse.
 *
 * NOTE: These tests use a fake [InMemorySyncStore] and [SyncFakeTransport].
 * No Android device, SharedPreferences, or network is required.
 */
class SyncManagerTest {

    private lateinit var store: InMemorySyncStore
    private lateinit var transport: SyncFakeTransport

    @Before
    fun setup() {
        store = InMemorySyncStore()
        transport = SyncFakeTransport()
    }

    // ---- Consent ----

    @Test
    fun `sync skips when consent is not granted`() {
        store.consented = false
        val sm = SyncManager(store, transport)
        sm.syncNow()
        assertEquals(0, transport.sessionCreations)
        assertEquals(0, transport.eventsSent)
    }

    // ---- Session creation ----

    @Test
    fun `sync creates session on first run`() {
        store.consented = true
        store.setSessionId(null)
        store.append(makeCallEvent("evt-1"))

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(1, transport.sessionCreations)
        assertEquals("fake-session-1", store.getSessionId())
    }

    @Test
    fun `sync reuses existing session`() {
        store.consented = true
        store.setSessionId("existing-session")
        store.append(makeCallEvent("evt-1"))

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(0, transport.sessionCreations)  // no new session
        assertEquals(1, transport.eventsSent)
    }

    // ---- Upload ----

    @Test
    fun `pending events are uploaded in order`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-1"))
        store.append(makeCallEvent("evt-2"))
        store.append(makeCallEvent("evt-3"))

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(3, transport.eventsSent)
        assertEquals(listOf("evt-1", "evt-2", "evt-3"), transport.sentEventIds)
    }

    @Test
    fun `uploaded events are marked as uploaded`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-1"))
        store.append(makeCallEvent("evt-2"))

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertTrue(store.getPendingEventIds().isEmpty())
    }

    @Test
    fun `no pending events results in no upload`() {
        store.consented = true
        store.setSessionId("s1")

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(0, transport.eventsSent)
    }

    // ---- Failure / retry ----

    @Test
    fun `failed upload stops and leaves remaining events pending`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-ok"))
        store.append(makeCallEvent("evt-fail"))
        store.append(makeCallEvent("evt-after"))

        transport.failEventId = "evt-fail"

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(1, transport.eventsSent)  // only evt-ok uploaded
        assertEquals(listOf("evt-ok"), transport.sentEventIds)

        // evt-fail and evt-after remain pending
        val pending = store.getPendingEventIds()
        assertTrue(pending.contains("evt-fail"))
        assertTrue(pending.contains("evt-after"))
    }

    @Test
    fun `retry uploads previously failed events`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-1"))
        store.append(makeCallEvent("evt-fail"))
        store.append(makeCallEvent("evt-3"))

        // First sync: evt-fail fails
        transport.failEventId = "evt-fail"
        val sm = SyncManager(store, transport)
        sm.syncNow()
        assertEquals(1, transport.eventsSent)

        // Second sync: all succeed
        transport.failEventId = null
        transport.eventsSent = 0
        transport.sentEventIds = mutableListOf()
        sm.syncNow()
        assertEquals(2, transport.eventsSent)  // evt-fail + evt-3
        assertEquals(listOf("evt-fail", "evt-3"), transport.sentEventIds)
    }

    // ---- Session creation failure ----

    @Test
    fun `session creation failure leaves events pending`() {
        store.consented = true
        store.setSessionId(null)
        store.append(makeCallEvent("evt-1"))

        transport.sessionCreationFails = true

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(0, transport.eventsSent)
        assertTrue(store.getPendingEventIds().contains("evt-1"))
    }

    // ---- Transport not configured ----

    @Test
    fun `not-configured transport stops sync`() {
        store.consented = true
        store.setSessionId(null)
        store.append(makeCallEvent("evt-1"))

        transport.notConfigured = true

        val sm = SyncManager(store, transport)
        sm.syncNow()

        assertEquals(0, transport.eventsSent)
    }

    // ---- Pending count ----

    @Test
    fun `pendingCount reflects remaining events`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-1"))
        store.append(makeCallEvent("evt-2"))

        val sm = SyncManager(store, transport)
        assertEquals(2, sm.pendingCount)

        sm.syncNow()
        assertEquals(0, sm.pendingCount)
    }

    // ---- Idempotency ----

    @Test
    fun `same event_id is not uploaded twice`() {
        store.consented = true
        store.setSessionId("s1")
        store.append(makeCallEvent("evt-1"))

        val sm = SyncManager(store, transport)

        // First sync
        sm.syncNow()
        assertEquals(1, transport.eventsSent)

        // Second sync — nothing pending
        transport.eventsSent = 0
        sm.syncNow()
        assertEquals(0, transport.eventsSent)
    }

    // ---- Helpers ----

    private fun makeCallEvent(eventId: String) = CallEvent(
        eventId = eventId,
        occurredAtMs = System.currentTimeMillis(),
        phase = CallPhase.CALL_END,
        direction = CallDirection.UNKNOWN,
        directionStatus = SignalStatus.UNKNOWN,
        startedAtMs = System.currentTimeMillis() - 5000,
        endedAtMs = System.currentTimeMillis(),
        durationMs = 5000,
        callerNumber = null,
        callerNumberStatus = SignalStatus.UNKNOWN,
        callerName = null,
        callerNameStatus = SignalStatus.NOT_AVAILABLE,
        isVideoCall = null,
        isVideoCallStatus = SignalStatus.NOT_AVAILABLE,
    )
}

// ---- Test doubles ----

/**
 * In-memory implementation of [SyncStore] for JVM tests.
 * Does not require Android Context / SharedPreferences.
 */
private class InMemorySyncStore : SyncStore {

    private val events = mutableMapOf<String, JSONObject>()
    private var counter = 0
    private var _sessionId: String? = null
    var consented = false
    private val pendingIds = mutableListOf<String>()

    fun append(event: CallEvent): Int {
        counter++
        events[event.eventId] = event.toJson()
        if (!pendingIds.contains(event.eventId)) {
            pendingIds.add(event.eventId)
        }
        return counter
    }

    override fun hasConsent(): Boolean = consented

    override fun getSessionId(): String? = _sessionId

    override fun setSessionId(sessionId: String?) {
        _sessionId = sessionId
    }

    override fun getPendingEventIds(): List<String> = pendingIds.toList()

    override fun markUploaded(eventId: String) {
        pendingIds.remove(eventId)
    }

    override fun getEvent(eventId: String): JSONObject? = events[eventId]
}

/**
 * Fake transport that records calls and can simulate failures.
 */
private class SyncFakeTransport : LuminaTransport {

    var sessionCreations = 0
    var eventsSent = 0
    var sentEventIds = mutableListOf<String>()
    var failEventId: String? = null
    var sessionCreationFails = false
    var notConfigured = false

    override fun createSession(): CreateSessionResult {
        if (notConfigured) return CreateSessionResult.NotConfigured
        if (sessionCreationFails) return CreateSessionResult.Failed("simulated failure")
        sessionCreations++
        return CreateSessionResult.Success("fake-session-$sessionCreations")
    }

    override fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult {
        if (notConfigured) return SendResult.NotConfigured
        val eventId = eventBody.optString("event_id", "")
        if (eventId == failEventId) return SendResult.Failed("simulated failure for $eventId")
        eventsSent++
        sentEventIds.add(eventId)
        return SendResult.Sent(200)
    }

    override fun addObservation(sessionId: String, body: JSONObject): ObservationResult {
        return ObservationResult.NotConfigured
    }

    override fun getDecision(sessionId: String): DecisionFetchResult {
        return DecisionFetchResult.NotConfigured
    }

    override fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult {
        return UserResponseResult.NotConfigured
    }
}
