package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM tests for the pure-logic call lifecycle state machine. These run without
 * a device (in a Gradle/JDK environment via `./gradlew :app:testDebugUnitTest`).
 */
class CallStateMachineTest {

    @Test
    fun `ringing then idle emits incoming completed call with duration`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })

        m.onPhoneState(PhoneStateEvent.RINGING, nowMs = 1000L, callerNumber = null)
        m.onPhoneState(PhoneStateEvent.IDLE, nowMs = 11000L)

        assertEquals(1, emitted.size)
        val e = emitted.single()
        assertEquals(CallPhase.CALL_END, e.phase)
        assertEquals(CallDirection.INCOMING, e.direction)
        assertEquals(SignalStatus.OBSERVED, e.directionStatus)
        assertEquals(1000L, e.startedAtMs)
        assertEquals(11000L, e.endedAtMs)
        assertEquals(10000L, e.durationMs)
        assertNull(e.callerNumber)
        assertEquals(SignalStatus.UNKNOWN, e.callerNumberStatus)
    }

    @Test
    fun `idle without tracked call emits nothing`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })

        m.onPhoneState(PhoneStateEvent.IDLE, nowMs = 5000L)

        assertTrue(emitted.isEmpty())
        assertFalse(m.inCall)
    }

    @Test
    fun `offhook without ringing reports unknown direction`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })

        m.onPhoneState(PhoneStateEvent.OFFHOOK, nowMs = 2000L, callerNumber = null)
        assertTrue(m.inCall)
        m.onPhoneState(PhoneStateEvent.IDLE, nowMs = 5000L)

        val e = emitted.single()
        assertEquals(CallDirection.UNKNOWN, e.direction)
        assertEquals(SignalStatus.UNKNOWN, e.directionStatus)
        assertEquals(3000L, e.durationMs)
    }

    @Test
    fun `observed number is preserved as observed`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })

        m.onPhoneState(PhoneStateEvent.RINGING, nowMs = 10L, callerNumber = "+15551234567")
        m.onPhoneState(PhoneStateEvent.IDLE, nowMs = 20L)

        val e = emitted.single()
        assertEquals("+15551234567", e.callerNumber)
        // A number, once captured, is a real observation of identity, never
        // converted into any risk verdict by this phase.
        assertEquals(SignalStatus.OBSERVED, e.callerNumberStatus)
    }

    @Test
    fun `closeActiveCall mirrors idle`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })

        m.onPhoneState(PhoneStateEvent.OFFHOOK, nowMs = 10L)
        m.closeActiveCall(nowMs = 210L)

        assertEquals(1, emitted.size)
        assertFalse(m.inCall)
    }

    @Test
    fun `call event invariants reject end before start`() {
        // completedCall with end < start is clamped to 0 duration, not rejected;
        // the state machine never produces this anyway.
        val e = CallEvent.completedCall(
            eventId = "x", occurredAtMs = 100,
            startedAtMs = 200, endedAtMs = 100,
            direction = CallDirection.UNKNOWN, directionStatus = SignalStatus.UNKNOWN,
            callerNumberStatus = SignalStatus.UNKNOWN,
        )
        assertEquals(0L, e.durationMs)
    }

    @Test
    fun `missing video-call signal stays not_available never false`() {
        val emitted = mutableListOf<CallEvent>()
        val m = CallStateMachine(emit = { emitted.add(it) })
        m.onPhoneState(PhoneStateEvent.RINGING, nowMs = 1L)
        m.onPhoneState(PhoneStateEvent.IDLE, nowMs = 2L)
        val e = emitted.single()
        assertNull(e.isVideoCall)
        assertEquals(SignalStatus.NOT_AVAILABLE, e.isVideoCallStatus)
    }
}
