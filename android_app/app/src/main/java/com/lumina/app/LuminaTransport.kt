package com.lumina.app

import android.util.Log
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Result of creating a backend session.
 */
sealed class CreateSessionResult {
    data class Success(val sessionId: String) : CreateSessionResult()
    data object NotConfigured : CreateSessionResult()
    data class Failed(val detail: String) : CreateSessionResult()
}

/**
 * Outcome of attempting to send an event to the backend.
 */
sealed class SendResult {
    data class Sent(val httpCode: Int) : SendResult()
    data object NotConfigured : SendResult()
    data class Failed(val detail: String) : SendResult()
}

/**
 * Result of adding an observation via the backend.
 */
sealed class ObservationResult {
    data class Success(val evidenceId: String) : ObservationResult()
    data object NotConfigured : ObservationResult()
    data class Failed(val detail: String) : ObservationResult()
}

/**
 * Result of fetching a decision from the backend.
 */
sealed class DecisionFetchResult {
    data class Success(val decisionJson: JSONObject) : DecisionFetchResult()
    data object NotConfigured : DecisionFetchResult()
    data class Failed(val detail: String) : DecisionFetchResult()
}

/**
 * Result of sending a user response via the backend.
 */
sealed class UserResponseResult {
    data object Success : UserResponseResult()
    data object NotConfigured : UserResponseResult()
    data class Failed(val detail: String) : UserResponseResult()
}

/**
 * Result of authenticating (401 from backend).
 */
sealed class AuthResult {
    data object Authenticated : AuthResult()
    data object NotConfigured : AuthResult()
    data class AuthFailed(val detail: String) : AuthResult()
}

/**
 * Result of creating an incident (CP-31 audio upload target).
 *
 * POST /api/incidents — returns the incident_id that the device owns, which
 * is then the required target for all audio evidence uploads.
 */
sealed class CreateIncidentResult {
    data class Success(val incidentId: String) : CreateIncidentResult()
    data object NotConfigured : CreateIncidentResult()
    data class Failed(val detail: String) : CreateIncidentResult()
}

/**
 * Outcome of uploading audio evidence.
 *
 * Honest, never fabricated:
 *  - [Success] carries exactly what the backend reported back.
 *  - [TooLarge] mirrors the backend 50 MB limit without attempting upload.
 *  - [Unsupported] mirrors the backend format whitelist.
 *  - [Invalid] is used for empty/undersized inputs rejected before network.
 *  - [AuthFailed] is a distinct class so it is never retried as a network
 *    failure (invalid credentials will keep failing).
 */
sealed class AudioUploadResult {
    data class Success(
        val incidentId: String,
        val transcriptId: String,
        val segmentsAccepted: Int,
    ) : AudioUploadResult()

    data object NotConfigured : AudioUploadResult()
    data class TooLarge(val maxBytes: Long) : AudioUploadResult()
    data class Unsupported(val detail: String) : AudioUploadResult()
    data class Invalid(val detail: String) : AudioUploadResult()
    data class AuthFailed(val detail: String) : AudioUploadResult()
    data class Failed(val detail: String) : AudioUploadResult()
}

/**
 * Transport abstraction for the Android -> backend boundary:
 *
 *   Android local event -> HTTPS -> backend session/event API
 *
 * Operations:
 *  1. [createSession]        -> POST /api/sessions
 *  2. [sendEvent]            -> POST /api/sessions/{session_id}/events
 *  3. [addObservation]       -> POST /api/sessions/{session_id}/observations
 *  4. [getDecision]          -> GET  /api/sessions/{session_id}/decision
 *  5. [sendResponse]         -> POST /api/sessions/{session_id}/respond
 *  6. [createIncident]       -> POST /api/incidents                (CP-31)
 *  7. [uploadAudio]          -> POST /api/incidents/{id}/audio     (CP-31)
 *
 * Hard rules:
 *  - HTTPS only (RFC-2606 placeholder treated as not configured)
 *  - No hardcoded secrets or tokens
 *  - No fabricated success
 *  - HMAC-SHA256 authentication on all protected endpoints
 *  - Auth failures classified distinctly from network failures
 *  - Audio is streamed from a temporary file and is never queued/persisted
 */
interface LuminaTransport {
    fun createSession(): CreateSessionResult
    fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult
    fun addObservation(sessionId: String, body: JSONObject): ObservationResult
    fun getDecision(sessionId: String): DecisionFetchResult
    fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult

    /**
     * Create an incident owned by this device (CP-31).
     *
     * Default implementations return NotConfigured so transport fakes used by
     * existing tests keep compiling; only the real HTTPS transport supports it.
     */
    fun createIncident(): CreateIncidentResult = CreateIncidentResult.NotConfigured

    /**
     * Upload an audio evidence file to the backend for STT (CP-31).
     *
     * @param incidentId  The owned incident created via [createIncident].
     * @param sourceFile  Temporary audio file. The implementor MUST NOT delete it;
     *                    ownership stays with the caller ([AudioUploader] deletes it).
     * @param contentType Multipart Content-Type for the file part.
     * @param idempotencyKey Stable retry key so a repeat upload is deduplicated.
     */
    fun uploadAudio(
        incidentId: String,
        sourceFile: java.io.File,
        contentType: String,
        idempotencyKey: String,
    ): AudioUploadResult = AudioUploadResult.NotConfigured
}

/**
 * HTTPS transport implementation with HMAC device authentication.
 *
 * Refuses to transmit unless a real https:// endpoint is configured.
 * Every protected request is signed with HMAC-SHA256 auth headers.
 *
 * Auth failures (HTTP 401) are classified as AUTH_FAILED in the result
 * and do NOT enter retry loops — they indicate invalid credentials,
 * not transient network issues.
 */
class HttpsLuminaTransport(
    private val configuredEndpoint: () -> String,
    private val isAllowedToSend: () -> Boolean,
    private val secretStore: SecretStore,
) : LuminaTransport {

    companion object {
        private const val TAG = "LUMINA.Transport"
        private const val CONNECT_TIMEOUT_MS = 10_000
        private const val READ_TIMEOUT_MS = 10_000
    }

    /**
     * Build auth headers for a request. Returns null if credentials not available.
     */
    private fun buildHeaders(method: String, path: String): Map<String, String>? {
        val deviceId = secretStore.getDeviceId() ?: return null
        val deviceSecret = secretStore.getDeviceSecret() ?: return null
        return DeviceAuth.buildAuthHeaders(deviceId, deviceSecret, method, path)
    }

    /**
     * Apply auth headers to an HttpURLConnection.
     * Returns false if credentials are not available.
     */
    private fun applyAuthHeaders(conn: HttpURLConnection, method: String, path: String): Boolean {
        val headers = buildHeaders(method, path) ?: return false
        for ((key, value) in headers) {
            conn.setRequestProperty(key, value)
        }
        return true
    }

    override fun createSession(): CreateSessionResult {
        if (!isAllowedToSend()) return CreateSessionResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return CreateSessionResult.NotConfigured

        val path = "/api/sessions"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return CreateSessionResult.Failed("Device not registered")
            }

            val body = JSONObject().toString().toByteArray(Charsets.UTF_8)
            conn.outputStream.use { it.write(body) }

            val code = conn.responseCode

            if (code in 200..299) {
                val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = JSONObject(responseBody)
                val sessionId = json.getString("session_id")
                CreateSessionResult.Success(sessionId)
            } else if (code == 401) {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Session creation auth failed: HTTP $code")
                CreateSessionResult.Failed("HTTP 401 (auth failed)")
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Session creation failed: HTTP $code, body: $errorBody")
                CreateSessionResult.Failed("HTTP $code")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Session creation failed", e)
            CreateSessionResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult {
        if (!isAllowedToSend()) return SendResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return SendResult.NotConfigured

        val path = "/api/sessions/$sessionId/events"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return SendResult.Failed("Device not registered")
            }

            conn.outputStream.use { it.write(eventBody.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            conn.disconnect()
            if (code in 200..299) SendResult.Sent(code) else SendResult.Failed("HTTP $code")
        } catch (e: Exception) {
            Log.e(TAG, "Event upload failed for session $sessionId", e)
            SendResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun addObservation(sessionId: String, body: JSONObject): ObservationResult {
        if (!isAllowedToSend()) return ObservationResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return ObservationResult.NotConfigured

        val path = "/api/sessions/$sessionId/observations"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return ObservationResult.Failed("Device not registered")
            }

            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode

            if (code in 200..299) {
                val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = JSONObject(responseBody)
                val evidenceId = json.optString("evidence_id", "")
                ObservationResult.Success(evidenceId)
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Add observation failed: HTTP $code, body: $errorBody")
                ObservationResult.Failed("HTTP $code")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Add observation failed for session $sessionId", e)
            ObservationResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun getDecision(sessionId: String): DecisionFetchResult {
        if (!isAllowedToSend()) return DecisionFetchResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return DecisionFetchResult.NotConfigured

        val path = "/api/sessions/$sessionId/decision"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS

            if (!applyAuthHeaders(conn, "GET", path)) {
                conn.disconnect()
                return DecisionFetchResult.Failed("Device not registered")
            }

            val code = conn.responseCode

            if (code in 200..299) {
                val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = JSONObject(responseBody)
                DecisionFetchResult.Success(json)
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Get decision failed: HTTP $code, body: $errorBody")
                DecisionFetchResult.Failed("HTTP $code")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Get decision failed for session $sessionId", e)
            DecisionFetchResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult {
        if (!isAllowedToSend()) return UserResponseResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return UserResponseResult.NotConfigured

        val path = "/api/sessions/$sessionId/respond"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return UserResponseResult.Failed("Device not registered")
            }

            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            conn.disconnect()
            if (code in 200..299) UserResponseResult.Success else UserResponseResult.Failed("HTTP $code")
        } catch (e: Exception) {
            Log.e(TAG, "Send response failed for session $sessionId", e)
            UserResponseResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun createIncident(): CreateIncidentResult {
        if (!isAllowedToSend()) return CreateIncidentResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return CreateIncidentResult.NotConfigured

        val path = "/api/incidents"
        val url = "$endpoint$path"
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return CreateIncidentResult.Failed("Device not registered")
            }

            conn.outputStream.use { it.write("{}".toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            if (code in 200..299) {
                val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = JSONObject(responseBody)
                val incidentId = json.getString("incident_id")
                CreateIncidentResult.Success(incidentId)
            } else if (code == 401) {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Incident creation auth failed: HTTP $code")
                CreateIncidentResult.Failed("HTTP 401 (auth failed)")
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                Log.w(TAG, "Incident creation failed: HTTP $code, body: $errorBody")
                CreateIncidentResult.Failed("HTTP $code")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Incident creation failed", e)
            CreateIncidentResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    override fun uploadAudio(
        incidentId: String,
        sourceFile: File,
        contentType: String,
        idempotencyKey: String,
    ): AudioUploadResult {
        if (!isAllowedToSend()) return AudioUploadResult.NotConfigured
        val endpoint = configuredEndpoint()
        if (!isRealEndpoint(endpoint)) return AudioUploadResult.NotConfigured
        if (!sourceFile.exists()) return AudioUploadResult.Invalid("Audio file does not exist")

        val path = "/api/incidents/$incidentId/audio"
        val url = "$endpoint$path"

        // Build the multipart layout up front so Content-Length is exact.
        val boundary = AudioMultipartBody.generateBoundary(DeviceAuth.generateNonce())
        val header = AudioMultipartBody.filePartHeader(sourceFile.name, contentType, boundary)
        val closing = AudioMultipartBody.closingBoundary(boundary)
        val headerBytes = AudioMultipartBody.utf8Length(header)
        val closingBytes = AudioMultipartBody.utf8Length(closing)
        val fileSizeBytes = sourceFile.length()
        val totalLength = AudioMultipartBody.contentLength(fileSizeBytes, headerBytes, closingBytes)

        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            conn.setRequestProperty("X-Idempotency-Key", idempotencyKey)
            conn.connectTimeout = CONNECT_TIMEOUT_MS
            conn.readTimeout = READ_TIMEOUT_MS
            conn.doOutput = true
            conn.setFixedLengthStreamingMode(totalLength)

            if (!applyAuthHeaders(conn, "POST", path)) {
                conn.disconnect()
                return AudioUploadResult.Failed("Device not registered")
            }

            BufferedOutputStream(conn.outputStream).use { out ->
                out.write(header.toByteArray(Charsets.UTF_8))
                FileInputStream(sourceFile).use { input ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        out.write(buffer, 0, read)
                    }
                }
                out.write(closing.toByteArray(Charsets.UTF_8))
            }

            val code = conn.responseCode
            if (code in 200..299) {
                val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = JSONObject(responseBody)
                AudioUploadResult.Success(
                    incidentId = json.getString("incident_id"),
                    transcriptId = json.optString("transcript_id", ""),
                    segmentsAccepted = json.optInt("segments_accepted", 0),
                )
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                when (code) {
                    401 -> {
                        Log.w(TAG, "Audio upload auth failed: HTTP 401")
                        AudioUploadResult.AuthFailed("HTTP 401 (auth failed)")
                    }
                    422 -> {
                        Log.w(TAG, "Audio upload rejected: HTTP 422, body: $errorBody")
                        AudioUploadResult.Failed("HTTP 422 — $errorBody")
                    }
                    else -> {
                        Log.w(TAG, "Audio upload failed: HTTP $code, body: $errorBody")
                        AudioUploadResult.Failed("HTTP $code")
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Audio upload failed for incident $incidentId", e)
            AudioUploadResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    private fun isRealEndpoint(endpoint: String): Boolean {
        val lower = endpoint.lowercase()
        return lower.startsWith("https://") &&
            !endpoint.contains("example.invalid", ignoreCase = true) &&
            endpoint.length > "https://".length
    }
}
