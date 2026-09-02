package com.lumina.app

/**
 * Explicit, deterministic adapter between the Android [CallEvent] model and
 * the backend session/event API contract.
 *
 * Mapping:
 *   CallPhase.CALL_START  ->  event_type "CALL_STARTED"
 *   CallPhase.CALL_ACTIVE ->  event_type "CALL_ACTIVE"
 *   CallPhase.CALL_END    ->  event_type "CALL_ENDED"
 *
 * Preserved: event ID, timestamp, direction, duration (where genuinely
 * observed), and every signal status. Unknown / unavailable values are
 * sent as JSON null with their honest status — never converted to
 * false / 0 / empty string.
 */
object CallEventAdapter {

    /**
     * The JSON body for POST /api/sessions/{session_id}/events.
     */
    data class BackendEventBody(
        val eventType: String,
        val eventId: String,
        val source: String,
        val payload: Map<String, Any?>,
    )

    /**
     * Convert a [CallEvent] into the backend event API body.
     *
     * [sessionId] is the backend session to post against.
     * The returned [BackendEventBody] can be serialised to JSON and sent
     * via [LuminaTransport.sendEvent].
     */
    fun toBackendBody(event: CallEvent): BackendEventBody {
        return BackendEventBody(
            eventType = mapPhaseToEventType(event.phase),
            eventId = event.eventId,
            source = "device",
            payload = toPayload(event),
        )
    }

    /**
     * Build the payload map from a [CallEvent]. Every nullable field is
     * emitted as a nullable Any? so that JSON serialisation produces null
     * for absent values (never 0 / false / "").
     */
    fun toPayload(event: CallEvent): Map<String, Any?> = mapOf(
        "event_id" to event.eventId,
        "occurred_at_ms" to event.occurredAtMs,
        "phase" to event.phase.name,
        "direction" to event.direction.name,
        "direction_status" to event.directionStatus.description,
        "started_at_ms" to event.startedAtMs,
        "ended_at_ms" to event.endedAtMs,
        "duration_ms" to event.durationMs,
        "caller_number" to event.callerNumber,
        "caller_number_status" to event.callerNumberStatus.description,
        "caller_name" to event.callerName,
        "caller_name_status" to event.callerNameStatus.description,
        "is_video_call" to event.isVideoCall,
        "is_video_call_status" to event.isVideoCallStatus.description,
    )

    private fun mapPhaseToEventType(phase: CallPhase): String = when (phase) {
        CallPhase.CALL_START -> "CALL_STARTED"
        CallPhase.CALL_ACTIVE -> "CALL_ACTIVE"
        CallPhase.CALL_END -> "CALL_ENDED"
    }
}
