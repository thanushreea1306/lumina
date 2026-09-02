package com.lumina.app

import android.content.Context
import android.content.SharedPreferences

/**
 * Runtime configuration for LUMINA's network boundary.
 *
 * Hard rules:
 *  - No IP addresses, credentials, tokens or secrets are hardcoded anywhere.
 *  - The backend endpoint is user-configured (via the consent/configuration UI)
 *    and persisted in SharedPreferences. It defaults to an explicit placeholder
 *    that is obviously not a real server (`lumina.example.invalid` is reserved
 *    by RFC 2606 and resolves nowhere), so we can never silently hit a guessed
 *    address.
 *  - Transport is refused until a caller-provided `https://` endpoint is set.
 */
object LuminaConfig {
    const val DEFAULT_ENDPOINT = "https://lumina.example.invalid"

    private const val PREFS = "lumina_config"
    private const val KEY_ENDPOINT = "backend_endpoint"
    private const val KEY_CONSENTED = "user_consented"
    private const val KEY_CONSENT_VERSION = "consent_version"
    const val CURRENT_CONSENT_VERSION = 1

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun backendEndpoint(context: Context): String =
        prefs(context).getString(KEY_ENDPOINT, DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT

    fun setBackendEndpoint(context: Context, endpoint: String): Boolean {
        val trimmed = endpoint.trim().trimEnd('/')
        if (trimmed.lowercase().startsWith("https://") && trimmed.length > "https://".length) {
            prefs(context).edit().putString(KEY_ENDPOINT, trimmed).apply()
            return true
        }
        return false
    }

    /** True only when the user has explicitly consented at the current consent version. */
    fun hasUserConsent(context: Context): Boolean {
        val p = prefs(context)
        return p.getBoolean(KEY_CONSENTED, false) &&
            p.getInt(KEY_CONSENT_VERSION, 0) == CURRENT_CONSENT_VERSION
    }

    fun setUserConsent(context: Context, consented: Boolean) {
        prefs(context).edit()
            .putBoolean(KEY_CONSENTED, consented)
            .putInt(KEY_CONSENT_VERSION, CURRENT_CONSENT_VERSION)
            .apply()
    }
}
