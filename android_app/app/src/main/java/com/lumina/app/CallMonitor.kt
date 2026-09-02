package com.lumina.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat

/**
 * Real call-lifecycle capture. Registers a [PhoneStateListener] and reports
 * observed transitions to [CallStateMachine]; completed calls are written to
 * a [LocalEventStore] (device-only) and the [onEventCaptured] callback is
 * invoked so the caller can trigger upload.
 *
 * The caller (a foreground [LuminaService]) holds the capture lifetime.
 */
class CallMonitor(
    private val appContext: Context,
    private val store: LocalEventStore,
    private val onEventCaptured: ((CallEvent) -> Unit)? = null,
) {
    private val telephony: TelephonyManager =
        appContext.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager

    private val stateMachine = CallStateMachine { event ->
        store.append(event)
        onEventCaptured?.invoke(event)
    }

    private val listener = object : PhoneStateListener() {
        override fun onCallStateChanged(state: Int, phoneNumber: String?) {
            val event = when (state) {
                TelephonyManager.CALL_STATE_RINGING -> PhoneStateEvent.RINGING
                TelephonyManager.CALL_STATE_OFFHOOK -> PhoneStateEvent.OFFHOOK
                TelephonyManager.CALL_STATE_IDLE -> PhoneStateEvent.IDLE
                else -> null
            } ?: return

            // phoneNumber is only delivered under narrow platform conditions
            // (READ_CALL_LOG / privileged app / pre-API-29). We pass through
            // whatever the platform actually gave us; null is recorded as
            // UNKNOWN by the state machine.
            val number = phoneNumber?.takeIf { it.isNotBlank() && it != "unknown" }
            val now = System.currentTimeMillis()
            stateMachine.onPhoneState(event, now, number)
        }
    }

    fun start() {
        if (!hasPhoneStatePermission()) return
        telephony.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
    }

    fun stop() {
        telephony.listen(listener, PhoneStateListener.LISTEN_NONE)
        stateMachine.closeActiveCall(System.currentTimeMillis())
    }

    /** Number of completed calls recorded this session. */
    val recordedCallCount: Int get() = store.count()

    private fun hasPhoneStatePermission(): Boolean =
        ContextCompat.checkSelfPermission(
            appContext, Manifest.permission.READ_PHONE_STATE
        ) == PackageManager.PERMISSION_GRANTED
}
