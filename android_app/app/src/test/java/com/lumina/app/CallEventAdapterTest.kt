package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * JVM tests for [CallEventAdapter]. Pure-logic mapping tests — no device required.
 */
class CallEventAdapterTest {

    // ---- Event type mapping ----

    @Test
    fun `CALL_START maps to CALL_STARTED`() {
        val event = makeEvent(phase = CallPhase.CALL_START)
        val body = CallEventAdapter.toBackendBody(event)
        assertEquals("CALL_STARTED", body.eventType)
    }

    @Test
    fun `CALL_ACTIVE maps to CALL_ACTIVE`() {
        val event = makeEvent(phase = CallPhase.CALL_ACTIVE)
        val body = CallEventAdapter.toBackendBody(event)
        assertEquals("CALL_ACTIVE", body.eventType)
    }

    @Test
    fun `CALL_END maps to CALL_ENDED`() {
        val event = makeEvent(phase = CallPhase.CALL_END)
        val body = CallEventAdapter.toBackendBody(event)
        assertEquals("CALL_ENDED", body.eventType)
    }

    // ---- Source ----

    @Test
    fun `source is always device`() {
        val event = makeEvent()
        val body = CallEventAdapter.toBackendBody(event)
        assertEquals("device", body.source)
    }

    // ---- Payload fields ----

    @Test
    fun `payload preserves event_id`() {
        val event = makeEvent(eventId = "test-evt-42")
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("test-evt-42", payload["event_id"])
    }

    @Test
    fun `payload preserves phase`() {
        val event = makeEvent(phase = CallPhase.CALL_END)
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("CALL_END", payload["phase"])
    }

    @Test
    fun `payload preserves observed direction`() {
        val event = makeEvent(
            direction = CallDirection.INCOMING,
            directionStatus = SignalStatus.OBSERVED,
        )
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("INCOMING", payload["direction"])
        assertEquals("observed", payload["direction_status"])
    }

    @Test
    fun `payload preserves unknown direction`() {
        val event = makeEvent(
            direction = CallDirection.UNKNOWN,
            directionStatus = SignalStatus.UNKNOWN,
        )
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("UNKNOWN", payload["direction"])
        assertEquals("unknown", payload["direction_status"])
    }

    @Test
    fun `payload preserves duration when observed`() {
        val event = makeEvent(
            startedAtMs = 1000, endedAtMs = 11000,
            durationMs = 10000,
        )
        val payload = CallEventAdapter.toPayload(event)
        assertEquals(10000L, payload["duration_ms"])
    }

    @Test
    fun `payload null duration for non-completed event`() {
        val event = makeEvent(phase = CallPhase.CALL_START, durationMs = null)
        val payload = CallEventAdapter.toPayload(event)
        assertNull(payload["duration_ms"])
    }

    @Test
    fun `payload null caller number when not observed`() {
        val event = makeEvent(
            callerNumber = null,
            callerNumberStatus = SignalStatus.UNKNOWN,
        )
        val payload = CallEventAdapter.toPayload(event)
        assertNull(payload["caller_number"])
        assertEquals("unknown", payload["caller_number_status"])
    }

    @Test
    fun `payload preserves observed caller number`() {
        val event = makeEvent(
            callerNumber = "+15551234567",
            callerNumberStatus = SignalStatus.OBSERVED,
        )
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("+15551234567", payload["caller_number"])
        assertEquals("observed", payload["caller_number_status"])
    }

    @Test
    fun `payload preserves caller name status as not_available`() {
        val event = makeEvent()
        val payload = CallEventAdapter.toPayload(event)
        assertEquals("not_available", payload["caller_name_status"])
    }

    @Test
    fun `payload video call status is not_available by default`() {
        val event = makeEvent()
        val payload = CallEventAdapter.toPayload(event)
        assertNull(payload["is_video_call"])
        assertEquals("not_available", payload["is_video_call_status"])
    }

    // ---- Full body structure ----

    @Test
    fun `backend body contains all required fields`() {
        val event = makeEvent()
        val body = CallEventAdapter.toBackendBody(event)
        assertNotNull(body.eventType)
        assertNotNull(body.eventId)
        assertEquals("device", body.source)
        assertNotNull(body.payload)
        // Payload must contain all fields the backend adapter expects
        for (key in listOf("event_id", "occurred_at_ms", "phase", "direction",
            "direction_status", "started_at_ms", "ended_at_ms", "duration_ms",
            "caller_number", "caller_number_status", "caller_name",
            "caller_name_status", "is_video_call", "is_video_call_status")) {
            assert(body.payload.containsKey(key)) { "Missing payload key: $key" }
        }
    }

    // ---- Helper ----

    private fun makeEvent(
        eventId: String = "test-evt-1",
        phase: CallPhase = CallPhase.CALL_END,
        direction: CallDirection = CallDirection.INCOMING,
        directionStatus: SignalStatus = SignalStatus.OBSERVED,
        startedAtMs: Long = 1000,
        endedAtMs: Long = 11000,
        durationMs: Long? = 10000,
        callerNumber: String? = null,
        callerNumberStatus: SignalStatus = SignalStatus.UNKNOWN,
        callerName: String? = null,
        callerNameStatus: SignalStatus = SignalStatus.NOT_AVAILABLE,
        isVideoCall: Boolean? = null,
        isVideoCallStatus: SignalStatus = SignalStatus.NOT_AVAILABLE,
    ) = CallEvent(
        eventId = eventId,
        occurredAtMs = endedAtMs,
        phase = phase,
        direction = direction,
        directionStatus = directionStatus,
        startedAtMs = startedAtMs,
        endedAtMs = endedAtMs,
        durationMs = durationMs,
        callerNumber = callerNumber,
        callerNumberStatus = callerNumberStatus,
        callerName = callerName,
        callerNameStatus = callerNameStatus,
        isVideoCall = isVideoCall,
        isVideoCallStatus = isVideoCallStatus,
    )
}
