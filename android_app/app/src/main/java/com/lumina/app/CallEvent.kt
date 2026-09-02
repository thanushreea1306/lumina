package com.lumina.app

import org.json.JSONObject

/**
 * Honest presence semantics for signals we try to observe.
 *
 * LUMINA never collapses "missing" into 0 / false / empty string, because that
 * would falsely imply the signal was observed. These statuses are used instead.
 */
enum class SignalStatus(val description: String) {
    /** The signal was actually observed on device. */
    OBSERVED("observed"),

    /** The signal is genuinely unknown (e.g. a number we cannot read). */
    UNKNOWN("unknown"),

    /** Android provides no public, reliable API for this signal. */
    NOT_AVAILABLE("not_available"),

    /** The user did not grant the permission needed to observe it. */
    NOT_PERMITTED("not_permitted"),

    /** LUMINA does not collect this signal (out of the MVP contract). */
    NOT_COLLECTED("not_collected"),
}

/** Call direction. A normal app cannot always determine this reliably. */
enum class CallDirection {
    INCOMING,
    OUTGOING,
    UNKNOWN,
}

/** Which stage of the call lifecycle a transition refers to. */
enum class CallPhase {
    CALL_START,
    CALL_ACTIVE,
    CALL_END,
}

/** What Android delivery produced a given transition. */
enum class PhoneStateEvent {
    RINGING,
    OFFHOOK,
    IDLE,
}

/**
 * A single local, device-only record for one observed call transition or one
 * completed call. This is the minimal event model for Phase 2.
 *
 * Every nullable field carries a corresponding [SignalStatus]. When a field is
 * not observed, the status says so and the value must be null (never 0/false/"").
 *
 * When [completed] is true this record summarises a whole call: [startedAtMs]
 * and [endedAtMs] are both set and [durationMs] is non-null. Signal-level
 * records (a single transition) leave those null.
 */
data class CallEvent(
    val eventId: String,
    val occurredAtMs: Long,

    // ---- lifecycle metadata ----
    val phase: CallPhase,
    val direction: CallDirection,
    val directionStatus: SignalStatus,
    val startedAtMs: Long?,
    val endedAtMs: Long?,
    val durationMs: Long?,

    // ---- caller identity (honest: usually unavailable to a normal app) ----
    val callerNumber: String?,
    val callerNumberStatus: SignalStatus,
    val callerName: String?,
    val callerNameStatus: SignalStatus,

    // ---- things we deliberately do NOT collect in the MVP ----
    val isVideoCall: Boolean?,
    val isVideoCallStatus: SignalStatus = SignalStatus.NOT_AVAILABLE,
) {

    init {
        require(directionStatus != SignalStatus.OBSERVED || direction != CallDirection.UNKNOWN) {
            "direction marked OBSERVED but value is UNKNOWN"
        }
        if (durationMs != null) require(durationMs >= 0) { "duration must be non-negative" }
        // Note: startedAtMs > endedAtMs is allowed; completedCall() clamps
        // duration to 0. The state machine never produces this, but the
        // completedCall() factory handles it defensively.
    }

    /**
     * Missing-value handling: emit nullable fields as JSON null and expose each
     * one's status, so the backend preserves the "missing vs observed" contract.
     * We never convert absent data into 0 / false.
     */
    fun toJson(): JSONObject = JSONObject().apply {
        put("event_id", eventId)
        put("occurred_at_ms", occurredAtMs)
        put("phase", phase.name)
        put("direction", direction.name)
        put("direction_status", directionStatus.description)
        put("started_at_ms", startedAtMs ?: JSONObject.NULL)
        put("ended_at_ms", endedAtMs ?: JSONObject.NULL)
        put("duration_ms", durationMs ?: JSONObject.NULL)
        put("caller_number", callerNumber ?: JSONObject.NULL)
        put("caller_number_status", callerNumberStatus.description)
        put("caller_name", callerName ?: JSONObject.NULL)
        put("caller_name_status", callerNameStatus.description)
        put("is_video_call", isVideoCall ?: JSONObject.NULL)
        put("is_video_call_status", isVideoCallStatus.description)
    }

    companion object {
        /**
         * A summary record for a complete call whose number could not be read.
         * [phase] is [CallPhase.CALL_END].
         */
        fun completedCall(
            eventId: String,
            occurredAtMs: Long,
            startedAtMs: Long,
            endedAtMs: Long,
            direction: CallDirection,
            directionStatus: SignalStatus,
            callerNumber: String? = null,
            callerNumberStatus: SignalStatus,
        ): CallEvent = CallEvent(
            eventId = eventId,
            occurredAtMs = occurredAtMs,
            phase = CallPhase.CALL_END,
            direction = direction,
            directionStatus = directionStatus,
            startedAtMs = startedAtMs,
            endedAtMs = endedAtMs,
            durationMs = (endedAtMs - startedAtMs).coerceAtLeast(0),
            callerNumber = callerNumber,
            callerNumberStatus = callerNumberStatus,
            callerName = null,
            callerNameStatus = SignalStatus.NOT_AVAILABLE,
            isVideoCall = null,
            isVideoCallStatus = SignalStatus.NOT_AVAILABLE,
        )
    }
}
