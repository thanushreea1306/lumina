package com.lumina.app

import java.util.UUID

/**
 * Turns a stream of [PhoneStateEvent]s into truthful, minimal completed-call
 * records. Pure logic: no Android dependencies, so it is unit-testable without
 * a device.
 *
 * Truthful-by-construction rules used here:
 *  - RINGING is only observed for incoming calls, so seeing RINGING before an
 *    active call lets us mark the direction INCOMING. An active call that was
 *    never preceded by RINGING has UNKNOWN direction — we must not guess
 *    "outgoing".
 *  - The incoming number is only available under limited platform conditions;
 *    the receiver passes whatever it actually got (possibly null), which we
 *    record as UNKNOWN — never converted into a real number and never turned
 *    into a "scam" verdict.
 *  - A single record is emitted when a call ends (IDLE), carrying the session
 *    start/end and duration. This is the smallest real lifecycle representation.
 */
class CallStateMachine(
    private val emit: (CallEvent) -> Unit,
) {
    private var callStartedAtMs: Long? = null
    private var sawRinging: Boolean = false
    private var capturedNumber: String? = null

    /** True while a call is in progress (started but not yet ended). */
    val inCall: Boolean get() = callStartedAtMs != null

    /**
     * Feed one TelephonyManager phone-state change.
     *
     * @param event the platform state transition
     * @param nowMs device clock time of the transition
     * @param callerNumber the number delivered with this event, or null if the
     *   platform did not provide one (normal for most apps/APIs)
     */
    fun onPhoneState(event: PhoneStateEvent, nowMs: Long, callerNumber: String? = null) {
        when (event) {
            PhoneStateEvent.RINGING -> {
                sawRinging = true
                if (callStartedAtMs == null) callStartedAtMs = nowMs
                if (callerNumber != null && capturedNumber == null) capturedNumber = callerNumber
            }

            PhoneStateEvent.OFFHOOK -> {
                // First OFFHOOK without a preceding RINGING may be an outgoing
                // call, but we cannot confirm that reliably, so direction stays
                // UNKNOWN. The call is now active.
                if (callStartedAtMs == null) callStartedAtMs = nowMs
            }

            PhoneStateEvent.IDLE -> {
                closeCall(nowMs)
            }
        }
    }

    /** Forcibly close any in-progress call (e.g. when monitoring is stopped). */
    fun closeActiveCall(nowMs: Long) = closeCall(nowMs)

    private fun closeCall(nowMs: Long) {
        val start = callStartedAtMs
        callStartedAtMs = null
        if (start == null) {
            // IDLE with no tracked call: safe to ignore.
            sawRinging = false
            capturedNumber = null
            return
        }

        val direction = if (sawRinging) CallDirection.INCOMING else CallDirection.UNKNOWN
        val directionStatus =
            if (sawRinging) SignalStatus.OBSERVED else SignalStatus.UNKNOWN

        val numberStatus =
            if (capturedNumber != null) SignalStatus.OBSERVED else SignalStatus.UNKNOWN

        emit(
            CallEvent.completedCall(
                eventId = UUID.randomUUID().toString(),
                occurredAtMs = nowMs,
                startedAtMs = start,
                endedAtMs = nowMs,
                direction = direction,
                directionStatus = directionStatus,
                callerNumber = capturedNumber,
                callerNumberStatus = numberStatus,
            )
        )

        sawRinging = false
        capturedNumber = null
    }
}
