package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * JVM tests for the audio authorization state machine (CP-31).
 *
 * Encodes the honest consent rules:
 *   - Sources that cannot exist on the platform are UNAVAILABLE, never
 *     "authorized" just because a user presses grant.
 *   - Text/file sources need no manual permission and are AUTHORIZED.
 *   - The microphone requires an explicit RECORD_AUDIO grant; denial (once or
 *     permanent) is DENIED and never auto-retried.
 */
class AudioAuthorizationTest {

    private fun auth(
        source: AudioSourceType,
        granted: Boolean?,
        requested: Boolean = false,
        deniedForever: Boolean = false,
    ) = AudioAuthorization.evaluate(source, granted, requested, deniedForever)

    @Test
    fun `user provided recording is authorized without asking`() {
        assertEquals(
            AudioAuthorizationStatus.AUTHORIZED,
            auth(AudioSourceType.USER_PROVIDED_RECORDING, granted = null),
        )
    }

    @Test
    fun `typed transcript is authorized without asking`() {
        assertEquals(
            AudioAuthorizationStatus.AUTHORIZED,
            auth(AudioSourceType.USER_DICTATED, granted = null),
        )
    }

    @Test
    fun `forwarded message is authorized without asking`() {
        assertEquals(
            AudioAuthorizationStatus.AUTHORIZED,
            auth(AudioSourceType.MESSAGE_FORWARD, granted = null),
        )
    }

    @Test
    fun `system call audio is UNAVAILABLE even if permission was granted`() {
        assertEquals(
            AudioAuthorizationStatus.UNAVAILABLE,
            auth(AudioSourceType.SYSTEM_CALL_AUDIO, granted = true),
        )
    }

    @Test
    fun `voip call audio is UNAVAILABLE`() {
        assertEquals(
            AudioAuthorizationStatus.UNAVAILABLE,
            auth(AudioSourceType.VOIP_CALL_AUDIO, granted = true),
        )
    }

    @Test
    fun `microphone defaults to NOT_REQUESTED`() {
        assertEquals(
            AudioAuthorizationStatus.NOT_REQUESTED,
            auth(AudioSourceType.MICROPHONE, granted = null),
        )
    }

    @Test
    fun `microphone is REQUESTED once the prompt is pending`() {
        assertEquals(
            AudioAuthorizationStatus.REQUESTED,
            auth(AudioSourceType.MICROPHONE, granted = null, requested = true),
        )
    }

    @Test
    fun `microphone granted yields AUTHORIZED`() {
        assertEquals(
            AudioAuthorizationStatus.AUTHORIZED,
            auth(AudioSourceType.MICROPHONE, granted = true),
        )
    }

    @Test
    fun `microphone denied once yields DENIED`() {
        assertEquals(
            AudioAuthorizationStatus.DENIED,
            auth(AudioSourceType.MICROPHONE, granted = false),
        )
    }

    @Test
    fun `microphone denied permanently yields DENIED`() {
        assertEquals(
            AudioAuthorizationStatus.DENIED,
            auth(AudioSourceType.MICROPHONE, granted = false, deniedForever = true),
        )
    }

    @Test
    fun `permission reflects actual grant never implicit for microphone`() {
        // A not-yet-asked microphone is never treated as authorized.
        assertEquals(
            AudioAuthorizationStatus.NOT_REQUESTED,
            auth(AudioSourceType.MICROPHONE, granted = null),
        )
    }
}