package com.lumina.app

import android.util.Log
import java.security.SecureRandom
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Device authentication for LUMINA Android ↔ FastAPI transport.
 *
 * Implements HMAC-SHA256 request signing that matches the backend
 * canonical format EXACTLY:
 *
 *     message = "{device_id}:{timestamp}:{nonce}:{method}:{path}"
 *     signature = HMAC-SHA256(device_secret_bytes, message_bytes).hexdigest()
 *
 * Security properties:
 *  - Device identity (device_id binds requests to a registered device)
 *  - Request integrity (HMAC prevents tampering)
 *  - Replay prevention (nonce + timestamp window)
 *  - Constant-time comparison (hmac.compare_digest on backend)
 */
object DeviceAuth {

    private const val TAG = "LUMINA.DeviceAuth"
    private const val HMAC_ALGORITHM = "HmacSHA256"
    private const val NONCE_BYTES = 16  // 128 bits of randomness

    /**
     * Compute HMAC-SHA256 signature for a request.
     *
     * This MUST produce the same output as the backend's:
     * ```python
     * message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
     * hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
     * ```
     *
     * @param deviceSecret The hex-encoded device secret (from registration)
     * @param deviceId The device identifier
     * @param timestamp ISO-8601 UTC timestamp
     * @param nonce Random nonce for this request
     * @param method HTTP method (GET, POST)
     * @param path Request path (e.g., /api/sessions/abc/events)
     * @return Hex-encoded HMAC-SHA256 signature
     */
    fun computeSignature(
        deviceSecret: String,
        deviceId: String,
        timestamp: String,
        nonce: String,
        method: String,
        path: String,
    ): String {
        val message = "$deviceId:$timestamp:$nonce:$method:$path"
        val mac = Mac.getInstance(HMAC_ALGORITHM)
        val keyBytes = deviceSecret.toByteArray(Charsets.UTF_8)
        val keySpec = SecretKeySpec(keyBytes, HMAC_ALGORITHM)
        mac.init(keySpec)
        val signatureBytes = mac.doFinal(message.toByteArray(Charsets.UTF_8))
        return signatureBytes.joinToString("") { "%02x".format(it) }
    }

    /**
     * Generate a cryptographically random nonce.
     *
     * Format: 32 hex characters (16 bytes = 128 bits).
     * uniqueness is guaranteed by SecureRandom entropy.
     */
    fun generateNonce(): String {
        val bytes = ByteArray(NONCE_BYTES)
        SecureRandom().nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }

    /**
     * Generate current UTC timestamp in ISO-8601 format.
     *
     * Format must match Python's datetime.now(timezone.utc).isoformat():
     * "2024-09-02T10:00:00.123456+00:00"
     *
     * We use a format that produces the same string representation
     * as the Python backend expects.
     */
    fun currentTimestamp(): String {
        // Python's datetime.now(timezone.utc).isoformat() produces:
        // "2024-09-02T10:00:00.123456+00:00"
        // We need to match this exactly for timestamp validation.
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX", Locale.US)
        sdf.timeZone = TimeZone.getTimeZone("UTC")
        return sdf.format(Date())
    }

    /**
     * Build all required authentication headers for a request.
     *
     * @param deviceId The device identifier
     * @param deviceSecret The hex-encoded device secret
     * @param method HTTP method (GET, POST)
     * @param path Request path
     * @return Map of X-Device-ID, X-Timestamp, X-Nonce, X-Signature headers
     */
    fun buildAuthHeaders(
        deviceId: String,
        deviceSecret: String,
        method: String,
        path: String,
    ): Map<String, String> {
        val timestamp = currentTimestamp()
        val nonce = generateNonce()
        val signature = computeSignature(deviceSecret, deviceId, timestamp, nonce, method, path)

        return mapOf(
            "X-Device-ID" to deviceId,
            "X-Timestamp" to timestamp,
            "X-Nonce" to nonce,
            "X-Signature" to signature,
        )
    }

    /**
     * Register a new device with the backend.
     *
     * @param endpoint The backend HTTPS endpoint
     * @return RegistrationResult with device_id and device_secret, or failure
     */
    fun registerDevice(endpoint: String): RegistrationResult {
        if (!endpoint.lowercase().startsWith("https://")) {
            return RegistrationResult.Failed("Endpoint must be HTTPS")
        }
        if (endpoint.contains("example.invalid", ignoreCase = true)) {
            return RegistrationResult.Failed("Endpoint is not configured")
        }

        return try {
            val url = java.net.URL("$endpoint/api/devices/register")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = 10_000
            conn.readTimeout = 10_000
            conn.doOutput = true

            conn.outputStream.use { it.write("{}".toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            if (code in 200..299) {
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                val json = org.json.JSONObject(body)
                val deviceId = json.getString("device_id")
                val deviceSecret = json.getString("device_secret")
                RegistrationResult.Success(deviceId, deviceSecret)
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                RegistrationResult.Failed("HTTP $code")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Device registration failed", e)
            RegistrationResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }
}

/**
 * Result of device registration.
 */
sealed class RegistrationResult {
    data class Success(val deviceId: String, val deviceSecret: String) : RegistrationResult()
    data class Failed(val detail: String) : RegistrationResult()
}
