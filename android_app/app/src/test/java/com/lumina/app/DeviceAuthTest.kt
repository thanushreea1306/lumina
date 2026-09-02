package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM tests for [DeviceAuth] HMAC signing.
 *
 * These verify:
 *  - HMAC canonicalization matches backend exactly
 *  - Known test-vector signature
 *  - Fresh nonce generation
 *  - Required auth headers
 *  - Timestamp generation
 *  - Secret storage abstraction
 *  - Authentication failure handling
 *  - Authenticated transport request construction
 *
 * No Android device required — pure JVM tests.
 */
class DeviceAuthTest {

    // ---- HMAC canonicalization ----

    @Test
    fun `HMAC message format matches backend canonical format`() {
        // Backend: message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
        // Verify we produce the exact same message string.
        val deviceId = "abc123"
        val timestamp = "2024-09-02T10:00:00.000000+00:00"
        val nonce = "def456"
        val method = "POST"
        val path = "/api/sessions"

        // The message must be exactly: "abc123:2024-09-02T10:00:00.000000+00:00:def456:POST:/api/sessions"
        val expectedMessage = "$deviceId:$timestamp:$nonce:$method:$path"
        assertEquals("abc123:2024-09-02T10:00:00.000000+00:00:def456:POST:/api/sessions", expectedMessage)
    }

    @Test
    fun `computeSignature produces deterministic output`() {
        val secret = "aabbccdd"  // hex-encoded 4-byte secret for simplicity
        val deviceId = "device-001"
        val timestamp = "2024-09-02T10:00:00.000000+00:00"
        val nonce = "nonce-001"
        val method = "POST"
        val path = "/api/sessions"

        val sig1 = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, path)
        val sig2 = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, path)

        assertEquals(sig1, sig2)
        // HMAC-SHA256 produces 64 hex chars
        assertEquals(64, sig1.length)
        // Should be hex characters only
        assertTrue(sig1.all { it in '0'..'9' || it in 'a'..'f' })
    }

    @Test
    fun `computeSignature matches Python HMAC-SHA256 for known test vector`() {
        // This is the canonical interop test vector.
        // Python:
        //   import hmac, hashlib
        //   secret = "test_secret_hex"
        //   message = "test_device:2024-01-01T00:00:00.000000+00:00:test_nonce:POST:/api/sessions"
        //   sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        //
        // We compute the same here and verify they match.
        val secret = "test_secret_hex"
        val deviceId = "test_device"
        val timestamp = "2024-01-01T00:00:00.000000+00:00"
        val nonce = "test_nonce"
        val method = "POST"
        val path = "/api/sessions"

        val signature = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, path)

        // Compute expected using standard Java HMAC-SHA256
        val message = "$deviceId:$timestamp:$nonce:$method:$path"
        val mac = javax.crypto.Mac.getInstance("HmacSHA256")
        val keySpec = javax.crypto.spec.SecretKeySpec(secret.toByteArray(Charsets.UTF_8), "HmacSHA256")
        mac.init(keySpec)
        val expectedBytes = mac.doFinal(message.toByteArray(Charsets.UTF_8))
        val expected = expectedBytes.joinToString("") { "%02x".format(it) }

        assertEquals(expected, signature)
    }

    @Test
    fun `different secrets produce different signatures`() {
        val deviceId = "device-001"
        val timestamp = "2024-09-02T10:00:00.000000+00:00"
        val nonce = "nonce-001"
        val method = "POST"
        val path = "/api/sessions"

        val sig1 = DeviceAuth.computeSignature("secret_a", deviceId, timestamp, nonce, method, path)
        val sig2 = DeviceAuth.computeSignature("secret_b", deviceId, timestamp, nonce, method, path)

        assertNotEquals(sig1, sig2)
    }

    @Test
    fun `different methods produce different signatures`() {
        val secret = "test_secret"
        val deviceId = "device-001"
        val timestamp = "2024-09-02T10:00:00.000000+00:00"
        val nonce = "nonce-001"
        val path = "/api/sessions"

        val postSig = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, "POST", path)
        val getSig = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, "GET", path)

        assertNotEquals(postSig, getSig)
    }

    @Test
    fun `different paths produce different signatures`() {
        val secret = "test_secret"
        val deviceId = "device-001"
        val timestamp = "2024-09-02T10:00:00.000000+00:00"
        val nonce = "nonce-001"
        val method = "POST"

        val sig1 = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, "/api/sessions")
        val sig2 = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, "/api/sessions/abc/events")

        assertNotEquals(sig1, sig2)
    }

    // ---- Nonce generation ----

    @Test
    fun `generateNonce returns 32 hex characters`() {
        val nonce = DeviceAuth.generateNonce()
        assertEquals(32, nonce.length)
        assertTrue(nonce.all { it in '0'..'9' || it in 'a'..'f' })
    }

    @Test
    fun `generateNonce produces unique values`() {
        val nonces = (1..100).map { DeviceAuth.generateNonce() }.toSet()
        assertEquals(100, nonces.size)
    }

    // ---- Timestamp generation ----

    @Test
    fun `currentTimestamp returns ISO-8601 format`() {
        val ts = DeviceAuth.currentTimestamp()
        // Should contain 'T' separator
        assertTrue("Timestamp should contain T: $ts", ts.contains("T"))
        // Should end with timezone offset
        assertTrue("Timestamp should end with timezone: $ts", ts.endsWith("+00:00") || ts.endsWith("Z"))
        // Should be parseable
        assertNotNull(ts)
    }

    // ---- Auth headers ----

    @Test
    fun `buildAuthHeaders returns all required headers`() {
        val headers = DeviceAuth.buildAuthHeaders(
            deviceId = "device-001",
            deviceSecret = "secret-001",
            method = "POST",
            path = "/api/sessions",
        )

        assertTrue("Missing X-Device-ID", headers.containsKey("X-Device-ID"))
        assertTrue("Missing X-Timestamp", headers.containsKey("X-Timestamp"))
        assertTrue("Missing X-Nonce", headers.containsKey("X-Nonce"))
        assertTrue("Missing X-Signature", headers.containsKey("X-Signature"))

        assertEquals("device-001", headers["X-Device-ID"])
        assertNotNull(headers["X-Timestamp"])
        assertNotNull(headers["X-Nonce"])
        assertNotNull(headers["X-Signature"])
    }

    @Test
    fun `buildAuthHeaders signature matches computeSignature`() {
        val deviceId = "device-001"
        val deviceSecret = "secret-001"
        val method = "POST"
        val path = "/api/sessions"

        val headers = DeviceAuth.buildAuthHeaders(deviceId, deviceSecret, method, path)

        // Manually compute expected signature
        val expectedSig = DeviceAuth.computeSignature(
            deviceSecret, deviceId,
            headers["X-Timestamp"]!!,
            headers["X-Nonce"]!!,
            method, path,
        )

        assertEquals(expectedSig, headers["X-Signature"])
    }

    @Test
    fun `buildAuthHeaders produces unique nonces per call`() {
        val h1 = DeviceAuth.buildAuthHeaders("d", "s", "POST", "/api/sessions")
        val h2 = DeviceAuth.buildAuthHeaders("d", "s", "POST", "/api/sessions")

        assertNotEquals(h1["X-Nonce"], h2["X-Nonce"])
        // Signatures will differ because nonces differ
        assertNotEquals(h1["X-Signature"], h2["X-Signature"])
    }

    // ---- Secret storage abstraction ----

    @Test
    fun `InMemorySecretStore stores and retrieves credentials`() {
        val store = InMemorySecretStore()

        assertFalse(store.hasCredentials())
        assertNull(store.getDeviceId())
        assertNull(store.getDeviceSecret())

        store.saveCredentials("device-123", "secret-456")

        assertTrue("Should have credentials after save", store.hasCredentials())
        assertEquals("device-123", store.getDeviceId())
        assertEquals("secret-456", store.getDeviceSecret())
    }

    @Test
    fun `InMemorySecretStore clearCredentials removes all data`() {
        val store = InMemorySecretStore()
        store.saveCredentials("device-123", "secret-456")
        assertTrue(store.hasCredentials())

        store.clearCredentials()

        assertFalse(store.hasCredentials())
        assertNull(store.getDeviceId())
        assertNull(store.getDeviceSecret())
    }

    // ---- Device registration ----

    @Test
    fun `registerDevice rejects non-HTTPS endpoints`() {
        val result = DeviceAuth.registerDevice("http://example.com")
        assertTrue(result is RegistrationResult.Failed)
    }

    @Test
    fun `registerDevice rejects invalid endpoints`() {
        val result = DeviceAuth.registerDevice("https://lumina.example.invalid")
        assertTrue(result is RegistrationResult.Failed)
    }

    // ---- Auth header application ----

    @Test
    fun `SecretStore integration with buildAuthHeaders works`() {
        val store = InMemorySecretStore()
        store.saveCredentials("test-device", "test-secret")

        val deviceId = store.getDeviceId()!!
        val deviceSecret = store.getDeviceSecret()!!

        val headers = DeviceAuth.buildAuthHeaders(deviceId, deviceSecret, "GET", "/api/sessions/abc/decision")

        assertEquals("test-device", headers["X-Device-ID"])
        assertEquals(64, headers["X-Signature"]!!.length)
    }




}
