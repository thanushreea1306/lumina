package com.lumina.app

/**
 * Honest capability model for where audio can come from on Android.
 *
 * This mirrors the backend's static capability matrix (app/incident/audio_source.py)
 * and is deliberately NOT aspirational. It documents what the Android platform
 * genuinely provides through public APIs that a normal third-party app can use.
 *
 * PLATFORM TRUTH (Android):
 *   - USER_PROVIDED_RECORDING: user-selectable files -> AVAILABLE (highest trust)
 *   - MICROPHONE: RECORD_AUDIO -> AVAILABLE, but captures LOCAL_ONLY.
 *     On speakerphone the microphone may partially pick up the remote party,
 *     but that is NOT guaranteed and must never be presented as call capture.
 *   - SYSTEM_CALL_AUDIO: NOT_AVAILABLE. Android exposes no public API for a
 *     third-party app to capture both sides of a cellular call. LUMINA never
 *     uses AccessibilityService tricks, system signatures, or hidden recording.
 *   - VOIP_CALL_AUDIO: NOT_AVAILABLE without per-app audio-routing integration.
 */
enum class AudioSourceType(val wireName: String) {
    USER_PROVIDED_RECORDING("USER_PROVIDED_RECORDING"),
    MICROPHONE("MICROPHONE"),
    USER_DICTATED("USER_DICTATED"),
    MESSAGE_FORWARD("MESSAGE_FORWARD"),
    SYSTEM_CALL_AUDIO("SYSTEM_CALL_AUDIO"),
    VOIP_CALL_AUDIO("VOIP_CALL_AUDIO"),
}

/** Whether a source is actually available, honestly. Never aspirational. */
enum class CapabilityStatus(val wireName: String) {
    AVAILABLE("AVAILABLE"),
    PARTIALLY_AVAILABLE("PARTIALLY_AVAILABLE"),
    NOT_AVAILABLE("NOT_AVAILABLE"),
    NOT_TESTED("NOT_TESTED"),
}

/** Which side(s) of a conversation a source captures. */
enum class AudioSide(val wireName: String) {
    LOCAL_ONLY("LOCAL_ONLY"),   // only the device-local microphone
    REMOTE_ONLY("REMOTE_ONLY"),
    BOTH_SIDES("BOTH_SIDES"),
    UNKNOWN("UNKNOWN"),
}

/**
 * One row in the Android audio source matrix.
 */
data class SourceCapability(
    val sourceType: AudioSourceType,
    val platform: String,
    val status: CapabilityStatus,
    val audioSide: AudioSide,
    val requiresPermission: String,
    val notes: String,
) {
    /** Keep the wire representation identical to the backend matrix. */
    fun toWireMap(): Map<String, String?> = mapOf(
        "source_type" to sourceType.wireName,
        "platform" to platform,
        "status" to status.wireName,
        "audio_side" to audioSide.wireName,
        "requires_permission" to requiresPermission,
        "android_version_constraint" to null,
        "notes" to notes,
    )
}

/**
 * The Android half of the platform capability matrix.
 *
 * The truth lives in one place so the UI and tests always agree.
 */
object AndroidAudioCapabilities {

    val MATRIX: List<SourceCapability> = listOf(
        SourceCapability(
            sourceType = AudioSourceType.USER_PROVIDED_RECORDING,
            platform = "android",
            status = CapabilityStatus.AVAILABLE,
            audioSide = AudioSide.UNKNOWN,
            requiresPermission = "none (user selects file)",
            notes = "User explicitly uploads a recording. Highest trust path.",
        ),
        SourceCapability(
            sourceType = AudioSourceType.MICROPHONE,
            platform = "android",
            status = CapabilityStatus.AVAILABLE,
            audioSide = AudioSide.LOCAL_ONLY,
            requiresPermission = "RECORD_AUDIO",
            notes = "Captures local microphone only. On speakerphone it may partially capture remote audio through the mic, but this is NOT guaranteed or reliable.",
        ),
        SourceCapability(
            sourceType = AudioSourceType.USER_DICTATED,
            platform = "android",
            status = CapabilityStatus.AVAILABLE,
            audioSide = AudioSide.UNKNOWN,
            requiresPermission = "none",
            notes = "User types what was said. Text-only path.",
        ),
        SourceCapability(
            sourceType = AudioSourceType.MESSAGE_FORWARD,
            platform = "android",
            status = CapabilityStatus.AVAILABLE,
            audioSide = AudioSide.UNKNOWN,
            requiresPermission = "none",
            notes = "User forwards chat messages. Text-only path.",
        ),
        SourceCapability(
            sourceType = AudioSourceType.SYSTEM_CALL_AUDIO,
            platform = "android",
            status = CapabilityStatus.NOT_AVAILABLE,
            audioSide = AudioSide.BOTH_SIDES,
            requiresPermission = "MODIFY_AUDIO_ROUTING (system signature only)",
            notes = "Android does NOT expose cellular call audio to third-party apps. LUMINA does not use AccessibilityService abuse or hidden recording.",
        ),
        SourceCapability(
            sourceType = AudioSourceType.VOIP_CALL_AUDIO,
            platform = "android",
            status = CapabilityStatus.NOT_AVAILABLE,
            audioSide = AudioSide.BOTH_SIDES,
            requiresPermission = "app-specific audio routing integration",
            notes = "Possible only if the VoIP app exposes audio streams. Requires per-app integration. Not generally available.",
        ),
    )

    /** Look up one source's capability on Android. Never null. */
    fun capability(source: AudioSourceType): SourceCapability =
        MATRIX.first { it.sourceType == source }

    /** Whether the source is genuinely usable right now. */
    fun isAvailable(source: AudioSourceType): Boolean =
        capability(source).status == CapabilityStatus.AVAILABLE

    fun requiresManualPermission(source: AudioSourceType): Boolean =
        source == AudioSourceType.MICROPHONE

    /** Sources the user can actually use (shown as enabled in the UI). */
    fun availableSources(): List<SourceCapability> =
        MATRIX.filter { it.status in
            (setOf(CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIALLY_AVAILABLE)) }

    /** Sources that are honestly unavailable (shown dimmed with a reason). */
    fun unavailableSources(): List<SourceCapability> =
        MATRIX.filter { it.status == CapabilityStatus.NOT_AVAILABLE }

    /**
     * Honest UI copy for a source. LUMINA never claims to be listening to a
     * phone call when it only has microphone or file audio.
     */
    fun honestUiText(source: AudioSourceType): String = when (source) {
        AudioSourceType.USER_PROVIDED_RECORDING ->
            "Analyzing your uploaded recording"
        AudioSourceType.MICROPHONE ->
            "Recording microphone audio"
        AudioSourceType.USER_DICTATED ->
            "Analyzing your transcript"
        AudioSourceType.MESSAGE_FORWARD ->
            "Analyzing forwarded messages"
        AudioSourceType.SYSTEM_CALL_AUDIO ->
            "System call audio is not available on this platform"
        AudioSourceType.VOIP_CALL_AUDIO ->
            "VoIP audio integration is not yet available"
    }
}

/**
 * Audio authorization states. Tracks the runtime-permission lifecycle for an
 * audio source with honest vocabulary: membership is about user consent, so a
 * permission that cannot exist (e.g. SYSTEM_CALL_AUDIO) is UNAVAILABLE, and a
 * permanent "don't ask again" denial is DENIED — never silently retried.
 */
enum class AudioAuthorizationStatus {
    /** Permission has not been requested yet. */
    NOT_REQUESTED,

    /** Permission prompt is pending (requested, no answer yet). */
    REQUESTED,

    /** The user granted the permission needed for this source. */
    AUTHORIZED,

    /** The user denied (either once or permanently). Never auto-retried. */
    DENIED,

    /** No permission exists for this source on this platform. */
    UNAVAILABLE,
}

/**
 * Pure, deterministic authorization resolution for an audio source.
 *
 * Rules:
 *  - Sources that are not available on the platform are always UNAVAILABLE,
 *    regardless of what the user approves.
 *  - Sources needing no manual permission (user-provided recording, typed
 *    transcript, forwarded message) are AUTHORIZED.
 *  - The microphone becomes AUTHORIZED only after RECORD_AUDIO is granted.
 *  - A permanent denial stays DENIED so we do not nag or auto-retry.
 */
object AudioAuthorization {

    fun evaluate(
        source: AudioSourceType,
        permissionGranted: Boolean?,
        permissionRequested: Boolean = false,
        permissionDeniedForever: Boolean = false,
    ): AudioAuthorizationStatus {
        if (!AdvancedAudioCapabilities.canEverBePermitted(source)) {
            return AudioAuthorizationStatus.UNAVAILABLE
        }
        if (!AndroidAudioCapabilities.requiresManualPermission(source)) {
            return AudioAuthorizationStatus.AUTHORIZED
        }
        return when {
            permissionGranted == true -> AudioAuthorizationStatus.AUTHORIZED
            permissionRequested -> AudioAuthorizationStatus.REQUESTED
            permissionDeniedForever -> AudioAuthorizationStatus.DENIED
            permissionGranted == false -> AudioAuthorizationStatus.DENIED
            else -> AudioAuthorizationStatus.NOT_REQUESTED
        }
    }
}

/**
 * Companion to [AndroidAudioCapabilities] answering "could this source ever be
 * permitted on this platform?" System call audio and VoIP audio are not
 * available to third-party apps, so no user permission can authorize them.
 */
object AdvancedAudioCapabilities {
    fun canEverBePermitted(source: AudioSourceType): Boolean =
        source != AudioSourceType.SYSTEM_CALL_AUDIO &&
            source != AudioSourceType.VOIP_CALL_AUDIO
}