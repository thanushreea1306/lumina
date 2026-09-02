package com.lumina.app

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Abstraction for secure device credential storage.
 *
 * The device_secret is received once during registration and must never
 * be transmitted again. It is stored encrypted and only decrypted in
 * memory when needed for HMAC signing.
 */
interface SecretStore {
    /** Store device credentials securely. */
    fun saveCredentials(deviceId: String, deviceSecret: String)

    /** Retrieve the stored device_id, or null if not registered. */
    fun getDeviceId(): String?

    /** Retrieve the stored device_secret, or null if not registered. */
    fun getDeviceSecret(): String?

    /** Whether credentials have been stored. */
    fun hasCredentials(): Boolean

    /** Clear all stored credentials (e.g., on consent revocation). */
    fun clearCredentials()
}

/**
 * Android Keystore-backed secret store.
 *
 * Uses AES-256-GCM encryption with a key stored in Android Keystore.
 * The device_secret is encrypted before being written to SharedPreferences.
 * Decryption happens only in memory when needed for HMAC signing.
 *
 * Security properties:
 *  - Encryption key is hardware-backed (Android Keystore)
 *  - Secret is never stored as plaintext in SharedPreferences
 *  - AES-GCM provides authenticated encryption (tamper detection)
 *  - Each encryption uses a fresh random IV
 *  - No secret is logged
 */
class KeystoreSecretStore(context: Context) : SecretStore {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val keyAlias = KEY_ALIAS

    init {
        // Ensure the encryption key exists in Android Keystore
        ensureKeyExists()
    }

    override fun saveCredentials(deviceId: String, deviceSecret: String) {
        try {
            val encryptedSecret = encrypt(deviceSecret)
            prefs.edit()
                .putString(KEY_DEVICE_ID, deviceId)
                .putString(KEY_ENCRYPTED_SECRET, encryptedSecret)
                .apply()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to encrypt and store credentials", e)
            throw SecurityException("Failed to store credentials securely", e)
        }
    }

    override fun getDeviceId(): String? {
        return prefs.getString(KEY_DEVICE_ID, null)
    }

    override fun getDeviceSecret(): String? {
        val encryptedSecret = prefs.getString(KEY_ENCRYPTED_SECRET, null) ?: return null
        return try {
            decrypt(encryptedSecret)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to decrypt device secret; credentials may be corrupted", e)
            null
        }
    }

    override fun hasCredentials(): Boolean {
        return getDeviceId() != null && prefs.contains(KEY_ENCRYPTED_SECRET)
    }

    override fun clearCredentials() {
        prefs.edit().clear().apply()
    }

    private fun ensureKeyExists() {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (!keyStore.containsAlias(keyAlias)) {
            val keyGen = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE
            )
            keyGen.init(
                KeyGenParameterSpec.Builder(
                    keyAlias,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
            keyGen.generateKey()
        }
    }

    private fun getSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        return keyStore.getKey(keyAlias, null) as SecretKey
    }

    /**
     * Encrypt a plaintext string using AES-256-GCM.
     * Returns Base64-encoded "iv:ciphertext" string.
     */
    private fun encrypt(plaintext: String): String {
        val cipher = Cipher.getInstance(AES_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getSecretKey())
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        // Prepend IV to ciphertext: base64(iv) + ":" + base64(ciphertext)
        val encodedIv = Base64.encodeToString(iv, Base64.NO_WRAP)
        val encodedCiphertext = Base64.encodeToString(ciphertext, Base64.NO_WRAP)
        return "$encodedIv:$encodedCiphertext"
    }

    /**
     * Decrypt a Base64-encoded "iv:ciphertext" string using AES-256-GCM.
     */
    private fun decrypt(encryptedData: String): String {
        val parts = encryptedData.split(":", limit = 2)
        if (parts.size != 2) throw IllegalArgumentException("Invalid encrypted data format")
        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[1], Base64.NO_WRAP)
        val cipher = Cipher.getInstance(AES_TRANSFORMATION)
        val spec = GCMParameterSpec(128, iv)
        cipher.init(Cipher.DECRYPT_MODE, getSecretKey(), spec)
        val plaintext = cipher.doFinal(ciphertext)
        return String(plaintext, Charsets.UTF_8)
    }

    companion object {
        private const val TAG = "LUMINA.KeystoreStore"
        private const val PREFS_NAME = "lumina_device_credentials"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_ENCRYPTED_SECRET = "encrypted_device_secret"
        private const val KEY_ALIAS = "lumina_device_key"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val AES_TRANSFORMATION = "AES/GCM/NoPadding"
    }
}

/**
 * SharedPreferences-based secret store (fallback for testing or older devices).
 *
 * The secret is stored in app-private SharedPreferences (MODE_PRIVATE),
 * which is inaccessible to other apps on non-rooted devices.
 *
 * WARNING: On rooted devices, SharedPreferences can be read. For production,
 * prefer [KeystoreSecretStore].
 */
class SharedPreferencesSecretStore(context: Context) : SecretStore {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    override fun saveCredentials(deviceId: String, deviceSecret: String) {
        prefs.edit()
            .putString(KEY_DEVICE_ID, deviceId)
            .putString(KEY_DEVICE_SECRET, deviceSecret)
            .apply()
    }

    override fun getDeviceId(): String? {
        return prefs.getString(KEY_DEVICE_ID, null)
    }

    override fun getDeviceSecret(): String? {
        return prefs.getString(KEY_DEVICE_SECRET, null)
    }

    override fun hasCredentials(): Boolean {
        return getDeviceId() != null && getDeviceSecret() != null
    }

    override fun clearCredentials() {
        prefs.edit().clear().apply()
    }

    companion object {
        private const val PREFS_NAME = "lumina_device_credentials"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_DEVICE_SECRET = "device_secret"
    }
}

/**
 * In-memory secret store for JVM tests. No persistence, no encryption.
 * Does NOT require Android Context.
 */
class InMemorySecretStore : SecretStore {
    private var deviceId: String? = null
    private var deviceSecret: String? = null

    override fun saveCredentials(deviceId: String, deviceSecret: String) {
        this.deviceId = deviceId
        this.deviceSecret = deviceSecret
    }

    override fun getDeviceId(): String? = deviceId

    override fun getDeviceSecret(): String? = deviceSecret

    override fun hasCredentials(): Boolean =
        deviceId != null && deviceSecret != null

    override fun clearCredentials() {
        deviceId = null
        deviceSecret = null
    }
}
