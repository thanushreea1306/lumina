package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM tests for the Android audio capability matrix (CP-31).
 *
 * These encode the PLATFORM TRUTH contract:
 *   - SYSTEM_CALL_AUDIO and VOIP_CALL_AUDIO are NOT_AVAILABLE on Android.
 *   - MICROPHONE is LOCAL_ONLY and the UI copy never claims call capture.
 *   - USER_PROVIDED_RECORDING / USER_DICTATED / MESSAGE_FORWARD are available.
 *   - The wire names match the backend matrix (app/incident/audio_source.py).
 *
 * If any of these ever flips to "available", the honest-experience guarantee
 * is broken and the test must fail.
 */
class AudioCapabilitiesTest {

    @Test
    fun `matrix covers every audio source type`() {
        val matrixTypes = AndroidAudioCapabilities.MATRIX.map { it.sourceType }.toSet()
        assertEquals(AudioSourceType.values().toSet(), matrixTypes)
    }

    @Test
    fun `system call audio is NOT available on android`() {
        val cap = AndroidAudioCapabilities.capability(AudioSourceType.SYSTEM_CALL_AUDIO)
        assertEquals(CapabilityStatus.NOT_AVAILABLE, cap.status)
        assertEquals(AudioSide.BOTH_SIDES, cap.audioSide)
        assertFalse(AndroidAudioCapabilities.isAvailable(AudioSourceType.SYSTEM_CALL_AUDIO))
    }

    @Test
    fun `voip call audio is NOT available on android`() {
        val cap = AndroidAudioCapabilities.capability(AudioSourceType.VOIP_CALL_AUDIO)
        assertEquals(CapabilityStatus.NOT_AVAILABLE, cap.status)
        assertFalse(AndroidAudioCapabilities.isAvailable(AudioSourceType.VOIP_CALL_AUDIO))
    }

    @Test
    fun `microphone is available but captures LOCAL_ONLY`() {
        val cap = AndroidAudioCapabilities.capability(AudioSourceType.MICROPHONE)
        assertEquals(CapabilityStatus.AVAILABLE, cap.status)
        assertEquals(AudioSide.LOCAL_ONLY, cap.audioSide)
        assertTrue(AndroidAudioCapabilities.isAvailable(AudioSourceType.MICROPHONE))
    }

    @Test
    fun `user provided recording and text paths are available`() {
        assertTrue(AndroidAudioCapabilities.isAvailable(AudioSourceType.USER_PROVIDED_RECORDING))
        assertTrue(AndroidAudioCapabilities.isAvailable(AudioSourceType.USER_DICTATED))
        assertTrue(AndroidAudioCapabilities.isAvailable(AudioSourceType.MESSAGE_FORWARD))
    }

    @Test
    fun `honest ui text for microphone never claims call capture`() {
        val text = AndroidAudioCapabilities.honestUiText(AudioSourceType.MICROPHONE)
        assertEquals("Recording microphone audio", text)
        assertFalse("Must not mention call capture: $text", text.contains("call", ignoreCase = true))
    }

    @Test
    fun `honest ui text for system call audio says not available`() {
        val text = AndroidAudioCapabilities.honestUiText(AudioSourceType.SYSTEM_CALL_AUDIO)
        assertTrue(text.contains("not available", ignoreCase = true))
    }

    @Test
    fun `only the microphone requires a manual runtime permission`() {
        for (type in AudioSourceType.values()) {
            assertEquals(
                "requiresManualPermission($type)",
                type == AudioSourceType.MICROPHONE,
                AndroidAudioCapabilities.requiresManualPermission(type),
            )
        }
    }

    @Test
    fun `toWireMap matches the backend wire contract`() {
        val mic = AndroidAudioCapabilities.capability(AudioSourceType.MICROPHONE).toWireMap()
        assertEquals("MICROPHONE", mic["source_type"])
        assertEquals("android", mic["platform"])
        assertEquals("AVAILABLE", mic["status"])
        assertEquals("LOCAL_ONLY", mic["audio_side"])
        assertEquals("RECORD_AUDIO", mic["requires_permission"])

        val systemCall = AndroidAudioCapabilities.capability(AudioSourceType.SYSTEM_CALL_AUDIO).toWireMap()
        assertEquals("NOT_AVAILABLE", systemCall["status"])
        assertEquals("BOTH_SIDES", systemCall["audio_side"])
    }

    @Test
    fun `unavailable list contains only genuinely missing sources`() {
        val unavailable = AndroidAudioCapabilities.unavailableSources().map { it.sourceType }.toSet()
        assertTrue(unavailable.contains(AudioSourceType.SYSTEM_CALL_AUDIO))
        assertTrue(unavailable.contains(AudioSourceType.VOIP_CALL_AUDIO))
        assertFalse(unavailable.contains(AudioSourceType.MICROPHONE))
        assertFalse(unavailable.contains(AudioSourceType.USER_PROVIDED_RECORDING))
    }
}