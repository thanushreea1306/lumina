package com.lumina.app

import java.io.File
import java.security.MessageDigest

/**
 * Uploader that bridges a temp audio file to the backend evidence pipeline.
 *
 * CP-31 contract (honest audio experience):
 *   - The source is a TEMPORARY file only (cacheDir). There is NO offline
 *     queue of raw audio: one attempt, then the temp file is deleted in a
 *     `finally` on every path — success, transport failure, validation error.
 *   - If the transport is not configured or the device is offline, the result
 *     is honest ([AudioUploadResult.NotConfigured]/[audio_upload_requires_connection])
 *     and the temp file is still deleted; nothing is persisted.
 *   - Client-side pre-flight mirrors the backend limits (50 MB, supported
 *     formats) so a user gets local feedback instead of a wasted upload.
 *   - The upload is idempotent: the retry key is derived deterministically
 *     from file metadata (name + size + lastModified), so re-running the same
 *     file maps to the same backend batch — the backend deduplicates.
 *   - No raw audio ever enters SharedPreferences, logs, or the metadata store.
 */
class AudioUploader(
    private val store: IncidentStore,
    private val transport: LuminaTransport,
) {

    /**
     * Return an incident owned by this device, creating one if needed.
     * The created id is persisted so later uploads reuse the same incident
     * (stable evidence history for the device's I'M TRAPPED/help flow).
     */
    fun ensureIncident(): CreateIncidentResult {
        store.getIncidentId()?.let { return CreateIncidentResult.Success(it) }
        val result = transport.createIncident()
        if (result is CreateIncidentResult.Success) {
            store.setIncidentId(result.incidentId)
        }
        return result
    }

    /**
     * Upload [tempFile] as audio evidence to the incident's `/audio` endpoint.
     *
     * Ownership of the temp file transfers here: it is ALWAYS deleted before
     * this method returns. Never reuse the file afterwards.
     */
    fun upload(incidentId: String, tempFile: File, contentType: String): AudioUploadResult {
        try {
            if (!tempFile.exists()) {
                return AudioUploadResult.Invalid("Audio file does not exist")
            }
            val size = tempFile.length()
            val validator = AudioUploadValidator.validate(tempFile.name, contentType, size)
            if (validator !is AudioUploadValidator.ValidationResult.Valid) {
                return validator.toResult()
            }

            val idempotencyKey = AudioIdempotencyKey.forFile(tempFile)
            return try {
                transport.uploadAudio(incidentId, tempFile, contentType, idempotencyKey)
            } catch (e: Exception) {
                AudioUploadResult.Failed(e.message ?: e.javaClass.simpleName)
            }
        } finally {
            deleteQuietly(tempFile)
        }
    }

    private fun deleteQuietly(file: File) {
        try {
            if (file.exists()) file.delete()
        } catch (_: Exception) {
            // Best effort: never leak an exception from cleanup.
        }
    }
}

/**
 * Client-side mirror of the backend's audio constraints
 * (app/incident/whisper_provider.py: SUPPORTED_EXTENSIONS, SUPPORTED_MIME_TYPES,
 * MAX_AUDIO_BYTES = 50 MB). Kept in one place so UI and tests agree.
 */
object AudioUploadValidator {
    const val MAX_AUDIO_BYTES = 50L * 1024 * 1024

    val SUPPORTED_EXTENSIONS = setOf(
        ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm", ".wma",
    )

    val SUPPORTED_MIME_TYPES = setOf(
        "audio/wav", "audio/wave", "audio/x-wav",
        "audio/mpeg", "audio/mp3",
        "audio/flac",
        "audio/ogg",
        "audio/x-m4a", "audio/mp4",
        "audio/webm",
        "audio/x-ms-wma",
    )

    fun extensionOf(fileName: String): String {
        val lower = fileName.lowercase()
        val idx = lower.lastIndexOf('.')
        return if (idx >= 0) lower.substring(idx) else ""
    }

    /** Best-effort MIME guess from a filename extension (backed up by extension validation). */
    fun mimeTypeFromName(fileName: String): String? =
        MIME_BY_EXTENSION[extensionOf(fileName)]

    private val MIME_BY_EXTENSION = mapOf(
        ".wav" to "audio/wav",
        ".mp3" to "audio/mpeg",
        ".flac" to "audio/flac",
        ".ogg" to "audio/ogg",
        ".m4a" to "audio/mp4",
        ".webm" to "audio/webm",
        ".wma" to "audio/x-ms-wma",
    )

    /** Honest pre-flight result. Never silently converts one error into another. */
    sealed class ValidationResult {
        object Valid : ValidationResult()
        data class TooLarge(val maxBytes: Long) : ValidationResult()
        data class Unsupported(val detail: String) : ValidationResult()
        data class Empty(val detail: String) : ValidationResult()

        fun toResult(): AudioUploadResult = when (this) {
            is TooLarge -> AudioUploadResult.TooLarge(maxBytes)
            is Unsupported -> AudioUploadResult.Unsupported(detail)
            is Empty -> AudioUploadResult.Invalid(detail)
            is Valid -> error("Valid has no error result")
        }
    }

    fun validate(fileName: String, contentType: String, sizeBytes: Long): ValidationResult {
        if (sizeBytes == 0L) {
            return ValidationResult.Empty("Audio file is empty")
        }
        if (sizeBytes > MAX_AUDIO_BYTES) {
            return ValidationResult.TooLarge(MAX_AUDIO_BYTES)
        }
        val ext = extensionOf(fileName)
        val mime = contentType.lowercase()
        if (ext !in SUPPORTED_EXTENSIONS && mime !in SUPPORTED_MIME_TYPES) {
            return ValidationResult.Unsupported(
                "Unsupported audio format: $fileName ($contentType). " +
                    "Supported: ${SUPPORTED_EXTENSIONS.sorted().joinToString(" ")}"
            )
        }
        return ValidationResult.Valid
    }
}

/**
 * Deterministic idempotency key for an upload attempt.
 *
 * Derived from file metadata (name + size + lastModified) so:
 *   - retrying the SAME file yields the SAME key  -> backend dedupes
 *   - a different file yields a different key     -> a distinct logical op
 * The key is scoped server-side to (owner, incident), so cross-owner reuse is
 * already impossible before this key is ever transmitted.
 */
object AudioIdempotencyKey {
    fun forFile(file: File): String {
        val raw = "${file.name}|${file.length()}|${file.lastModified()}"
        return sha256Hex(raw)
    }

    fun forMetadata(name: String, sizeBytes: Long, lastModifiedMs: Long): String =
        sha256Hex("$name|$sizeBytes|$lastModifiedMs")

    private fun sha256Hex(input: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(input.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }
}