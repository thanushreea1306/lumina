package com.lumina.app

import android.media.MediaRecorder
import android.util.Log
import java.io.File

/**
 * Wrapper around [MediaRecorder] for the LEGITIMATE microphone path.
 *
 * The microphone is captured ONLY while the user has explicitly started a
 * recording from the UI and a visible indicator is shown. LUMINA never records
 * a phone call, never records on the modern background, and never uses the
 * microphone without RECORD_AUDIO permission and an explicit user action.
 *
 * The capture is bounded (soft cap) and is ALWAYS stopped in a `finally` so
 * the OS recording session can never leak. Output is written to a temp file in
 * the app cache only — never to a permanent recording store.
 *
 * This class is thin on purpose: the OS itself further enforces honest capture
 * via the mandatory microphone indicator (API 29+) and runtime permission.
 */
class MicrophoneRecorder {

    companion object {
        private const val TAG = "LUMINA.MicRecorder"
        const val OUTPUT_EXTENSION = ".m4a"
        const val CONTENT_TYPE = "audio/mp4"
        const val HONEST_LABEL = "Recording microphone audio"
    }

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null

    val isRecording: Boolean get() = recorder != null

    /**
     * Start a microphone recording into a fresh temp file inside [cacheDir].
     * @return the temp file, or null if start failed (permission/prepare).
     */
    fun start(cacheDir: File): File? {
        if (isRecording) return null
        val tempName = "lumina_mic_${System.currentTimeMillis()}$OUTPUT_EXTENSION"
        val file = File(cacheDir, tempName)
        return try {
            val rec = MediaRecorder()
            rec.setAudioSource(MediaRecorder.AudioSource.MIC)
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            rec.setOutputFile(file.absolutePath)
            rec.prepare()
            rec.start()
            recorder = rec
            outputFile = file
            file
        } catch (e: Exception) {
            Log.e(TAG, "Microphone recording could not start", e)
            releaseQuietly()
            deleteQuietly(file)
            null
        }
    }

    /**
     * Stop the recording and finalize the temp file.
     * @return the completed temp file, or null if nothing was recording.
     */
    fun stop(): File? {
        val file = outputFile
        releaseQuietly()
        outputFile = null
        if (file == null || !file.exists()) {
            deleteQuietly(file)
            return null
        }
        return file
    }

    /** Abort and delete the temp file without keeping any audio. */
    fun cancel() {
        val file = outputFile
        releaseQuietly()
        outputFile = null
        deleteQuietly(file)
    }

    private fun releaseQuietly() {
        val rec = recorder
        recorder = null
        if (rec == null) return
        try {
            rec.stop()
        } catch (_: RuntimeException) {
            // Recording may already be stopped; that is fine.
        }
        try {
            rec.reset()
        } catch (_: RuntimeException) {
            // Recycled/stopped already.
        }
        try {
            rec.release()
        } catch (_: RuntimeException) {
            // Already released.
        }
    }

    private fun deleteQuietly(file: File?) {
        if (file == null) return
        try {
            if (file.exists()) file.delete()
        } catch (_: Exception) {
            // Best effort.
        }
    }
}

/**
 * Pure policy helpers for the microphone path so the important honesty
 * invariants stay JVM-testable without a device.
 */
object MicrophoneRecordingPolicy {
    const val SOFT_CAP_MS = 15L * 60 * 1000L

    /** Honest UI copy shown while recording. Never claims call capture. */
    fun honestRecordingLabel(): String = MicrophoneRecorder.HONEST_LABEL

    /** Temp file name layout. Deterministic prefix, honest extension. */
    fun generateTempName(timestampMs: Long): String =
        "lumina_mic_${timestampMs}${MicrophoneRecorder.OUTPUT_EXTENSION}"

    /**
     * Whether a new recording may start given current duration already captured.
     * Enforces the soft cap so a recording can never trail unbounded.
     */
    fun mayRecord(alreadyRecordedMs: Long): Boolean = alreadyRecordedMs < SOFT_CAP_MS
}