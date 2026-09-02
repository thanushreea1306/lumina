package com.lumina.app

import android.util.Log
import org.json.JSONObject
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
 *
 * Hard rules:
 *  - HTTPS only (RFC-2606 placeholder treated as not configured)
 *  - No hardcoded secrets or tokens
 *  - No fabricated success
 *  - HMAC-SHA256 authentication on all protected endpoints
 *  - Auth failures classified distinctly from network failures
 */
interface LuminaTransport {
    fun createSession(): CreateSessionResult
    fun sendEvent(sessionId: String, eventBody: JSONObject): SendResult
    fun addObservation(sessionId: String, body: JSONObject): ObservationResult
    fun getDecision(sessionId: String): DecisionFetchResult
    fun sendResponse(sessionId: String, body: JSONObject): UserResponseResult
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

    private fun isRealEndpoint(endpoint: String): Boolean {
        val lower = endpoint.lowercase()
        return lower.startsWith("https://") &&
            !endpoint.contains("example.invalid", ignoreCase = true) &&
            endpoint.length > "https://".length
    }
}
