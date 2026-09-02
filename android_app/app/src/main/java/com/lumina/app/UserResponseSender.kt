package com.lumina.app

import android.util.Log
import org.json.JSONObject

/**
 * Sends user responses to high-risk action requests via the backend.
 *
 * A response is only sent after the user explicitly chooses it.
 * The system NEVER automatically marks an action as performed.
 *
 * Backend contract: POST /api/sessions/{session_id}/respond
 * Request: { "action": "SHARE_OTP", "response": "performed" }
 */
class UserResponseSender(
    private val transport: LuminaTransport,
) {
    companion object {
        private const val TAG = "LUMINA.Response"
    }

    /**
     * Send a user response to the backend.
     * Returns true if the backend accepted the response.
     */
    fun sendResponse(sessionId: String, action: String, response: String): Boolean {
        val body = JSONObject().apply {
            put("action", action)
            put("response", response)
        }

        return when (val result = transport.sendResponse(sessionId, body)) {
            is UserResponseResult.Success -> {
                Log.d(TAG, "Response sent: $action -> $response")
                true
            }
            is UserResponseResult.Failed -> {
                Log.w(TAG, "Response failed: $action -> $response: ${result.detail}")
                false
            }
            is UserResponseResult.NotConfigured -> {
                Log.w(TAG, "Transport not configured; response not sent")
                false
            }
        }
    }
}
