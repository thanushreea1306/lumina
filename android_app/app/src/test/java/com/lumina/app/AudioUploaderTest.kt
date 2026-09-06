package com.lumina.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * JVM tests for [AudioUploader] (CP-31).
 *
 * Enforces the honest-audio contract:
 *   - Uploads always target the OWNED incident (created once, reused).
 *   - Temp audio files are ALWAYS deleted, including on validation failure,
 *     transport failure, and NotConfigured/offline — raw audio is never queued
 *     or persisted.
 *   - Client-side validation mirrors the backend (size + format), and the
 *     idempotency key is deterministic so a retry maps to the same backend batch.
 */
class AudioUploaderTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun makeWavFile(name: String = "test.wav", size: Int = 1024): File {
        val file = tmp.newFile(name)
        file.writeBytes(ByteArray(size) { 0 })
        file.setLastModified(1_600_000_000_000L)
        return file
    }

    // ---- Incident targeting ----

    @Test
    fun `ensureIncident reuses an existing incident without creating one`() {
        val store = InMemoryIncidentStore().apply { setIncidentId("inc-existing") }
        val transport = RecordingTransport()
        val uploader = AudioUploader(store, transport)

        val result = uploader.ensureIncident()

        assertTrue(result is CreateIncidentResult.Success)
        assertEquals("inc-existing", (result as CreateIncidentResult.Success).incidentId)
        assertEquals(0, transport.createdIncidents)
    }

    @Test
    fun `ensureIncident creates and persists a new incident once`() {
        val store = InMemoryIncidentStore()
        val transport = RecordingTransport().apply {
            createIncidentResult = CreateIncidentResult.Success("inc-new")
        }
        val uploader = AudioUploader(store, transport)

        val first = uploader.ensureIncident()
        val second = uploader.ensureIncident()

        assertTrue(first is CreateIncidentResult.Success)
        assertTrue(second is CreateIncidentResult.Success)
        assertEquals("inc-new", store.getIncidentId())
        assertEquals(1, transport.createdIncidents)
    }

    @Test
    fun `failed incident creation is honoured and never persisted`() {
        val store = InMemoryIncidentStore()
        val transport = RecordingTransport().apply {
            createIncidentResult = CreateIncidentResult.Failed("HTTP 500")
        }
        val uploader = AudioUploader(store, transport)

        val result = uploader.ensureIncident()

        assertTrue(result is CreateIncidentResult.Failed)
        assertEquals(null, store.getIncidentId())
    }

    // ---- Successful upload ----

    @Test
    fun `successful upload forwards metadata and deletes the temp file`() {
        val transport = RecordingTransport().apply {
            uploadResult = AudioUploadResult.Success("inc-1", "transcript-1", 3)
        }
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = makeWavFile()

        val result = uploader.upload("inc-1", file, "audio/wav")

        assertTrue(result is AudioUploadResult.Success)
        assertEquals("inc-1", transport.lastIncidentId)
        assertEquals("audio/wav", transport.lastContentType)
        assertEquals(file.absolutePath, transport.seenTempPath)
        assertEquals(1, transport.uploadCalls)
        assertFalse("temp file must be deleted after a successful upload", file.exists())
    }

    @Test
    fun `uploader derives a deterministic idempotency key for the same file`() {
        val transport = RecordingTransport().apply {
            uploadResult = AudioUploadResult.Success("inc-1", "t-1", 1)
        }
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = makeWavFile("same.wav")
        val expected = AudioIdempotencyKey.forMetadata(file.name, file.length(), file.lastModified())

        uploader.upload("inc-1", file, "audio/wav")

        assertEquals(expected, transport.lastIdempotencyKey)
        assertEquals(64, transport.lastIdempotencyKey!!.length)
    }

    // ---- Validation failures still clean up ----

    @Test
    fun `unsupported format is rejected before network and temp is deleted`() {
        val transport = RecordingTransport()
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = tmp.newFile("evil.exe").apply { writeBytes(byteArrayOf(1, 2, 3)) }

        val result = uploader.upload("inc-1", file, "application/octet-stream")

        assertTrue(result is AudioUploadResult.Unsupported)
        assertEquals(0, transport.uploadCalls)
        assertFalse("temp file must be deleted after a rejected upload", file.exists())
    }

    @Test
    fun `empty audio is rejected and temp is deleted`() {
        val transport = RecordingTransport()
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = tmp.newFile("empty.wav")

        val result = uploader.upload("inc-1", file, "audio/wav")

        assertTrue(result is AudioUploadResult.Invalid)
        assertEquals(0, transport.uploadCalls)
        assertFalse(file.exists())
    }

    @Test
    fun `validator rejects oversized audio before any upload`() {
        val result = AudioUploadValidator.validate(
            "big.wav", "audio/wav", AudioUploadValidator.MAX_AUDIO_BYTES + 1,
        )
        assertTrue(result is AudioUploadValidator.ValidationResult.TooLarge)
        val mapped = (result as AudioUploadValidator.ValidationResult.TooLarge).toResult()
        assertTrue(mapped is AudioUploadResult.TooLarge)
        assertEquals(AudioUploadValidator.MAX_AUDIO_BYTES, (mapped as AudioUploadResult.TooLarge).maxBytes)
    }

    // ---- Transport failures still clean up ----

    @Test
    fun `not configured upload still deletes the temp file`() {
        val transport = RecordingTransport().apply {
            uploadResult = AudioUploadResult.NotConfigured
        }
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = makeWavFile()

        val result = uploader.upload("inc-1", file, "audio/wav")

        assertEquals(AudioUploadResult.NotConfigured, result)
        assertFalse("offline upload must not persist raw audio", file.exists())
    }

    @Test
    fun `transport exception becomes Failed and temp is deleted`() {
        val transport = RecordingTransport().apply { uploadThrows = true }
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val file = makeWavFile()

        val result = uploader.upload("inc-1", file, "audio/wav")

        assertTrue(result is AudioUploadResult.Failed)
        assertFalse("temp file must be deleted even when transport throws", file.exists())
    }

    @Test
    fun `nonexistent temp file returns Invalid without calling transport`() {
        val transport = RecordingTransport()
        val uploader = AudioUploader(InMemoryIncidentStore(), transport)
        val ghost = File(tmp.root, "ghost.wav")

        val result = uploader.upload("inc-1", ghost, "audio/wav")

        assertTrue(result is AudioUploadResult.Invalid)
        assertEquals(0, transport.uploadCalls)
    }

    // ---- Validator + idempotency key pure logic ----

    @Test
    fun `validator accepts either a valid extension or a valid mime type`() {
        assertTrue(
            AudioUploadValidator.validate("clip.m4a", "application/octet-stream", 10) is
                AudioUploadValidator.ValidationResult.Valid
        )
        assertTrue(
            AudioUploadValidator.validate("clip.bin", "audio/webm", 10) is
                AudioUploadValidator.ValidationResult.Valid
        )
        assertTrue(
            AudioUploadValidator.validate("clip.bin", "something/else", 10) is
                AudioUploadValidator.ValidationResult.Unsupported
        )
    }

    @Test
    fun `mimeTypeFromName maps supported extensions to backend mimes`() {
        assertEquals("audio/wav", AudioUploadValidator.mimeTypeFromName("a.wav"))
        assertEquals("audio/mp4", AudioUploadValidator.mimeTypeFromName("a.m4a"))
        assertEquals("audio/webm", AudioUploadValidator.mimeTypeFromName("a.webm"))
        assertEquals(null, AudioUploadValidator.mimeTypeFromName("a.exe"))
    }

    @Test
    fun `idempotency key is stable for identical metadata`() {
        val k1 = AudioIdempotencyKey.forMetadata("same.wav", 1024, 1_600_000_000_000L)
        val k2 = AudioIdempotencyKey.forMetadata("same.wav", 1024, 1_600_000_000_000L)
        assertEquals(k1, k2)
        assertEquals(64, k1.length)
    }

    @Test
    fun `idempotency key changes when the file changes`() {
        val base = AudioIdempotencyKey.forMetadata("a.wav", 1024, 1_600_000_000_000L)
        assertNotEquals(base, AudioIdempotencyKey.forMetadata("a.wav", 2048, 1_600_000_000_000L))
        assertNotEquals(base, AudioIdempotencyKey.forMetadata("a.wav", 1024, 1_700_000_000_000L))
        assertNotEquals(base, AudioIdempotencyKey.forMetadata("b.wav", 1024, 1_600_000_000_000L))
    }
}

// ---- Test doubles ----

private class InMemoryIncidentStore : IncidentStore {
    private var incidentId: String? = null
    override fun getIncidentId(): String? = incidentId
    override fun setIncidentId(incidentId: String?) {
        this.incidentId = incidentId
    }
}

private class RecordingTransport : LuminaTransport {
    var createIncidentResult: CreateIncidentResult = CreateIncidentResult.Failed("not stubbed")
    var uploadResult: AudioUploadResult = AudioUploadResult.Failed("not stubbed")
    var uploadThrows = false

    var createdIncidents = 0
    var uploadCalls = 0
    var lastIncidentId: String? = null
    var lastContentType: String? = null
    var lastIdempotencyKey: String? = null
    var seenTempPath: String? = null

    override fun createSession(): CreateSessionResult = CreateSessionResult.NotConfigured

    override fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult =
        SendResult.NotConfigured

    override fun addObservation(sessionId: String, body: JSONObject): ObservationResult =
        ObservationResult.NotConfigured

    override fun getDecision(sessionId: String): DecisionFetchResult =
        DecisionFetchResult.NotConfigured

    override fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult =
        UserResponseResult.NotConfigured

    override fun createIncident(): CreateIncidentResult {
        createdIncidents++
        return createIncidentResult
    }

    override fun uploadAudio(
        incidentId: String,
        sourceFile: File,
        contentType: String,
        idempotencyKey: String,
    ): AudioUploadResult {
        uploadCalls++
        lastIncidentId = incidentId
        lastContentType = contentType
        lastIdempotencyKey = idempotencyKey
        seenTempPath = sourceFile.absolutePath
        if (uploadThrows) throw RuntimeException("simulated transport failure")
        return uploadResult
    }
}