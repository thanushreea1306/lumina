package com.lumina.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telephony.TelephonyManager
import android.util.Log

/**
 * Boot/Manifest-declared entry point for phone-state broadcasts.
 *
 * On a [TelephonyManager.ACTION_PHONE_STATE_CHANGED] broadcast it starts the
 * monitoring [LuminaService] so the call lifecycle is captured, but only when
 * the user has explicitly consented. All actual call capture happens inside the
 * foreground service's [CallMonitor]; this receiver only guarantees the service
 * is running. It never reads or reacts to the number on its own.
 */
class CallReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return

        if (!LuminaConfig.hasUserConsent(context)) {
            Log.d("LUMINA", "Phone-state received but user has not consented; no monitoring started")
            return
        }

        val serviceIntent = Intent(context, LuminaService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }
        } catch (e: IllegalStateException) {
            // Receivers on modern Android may not be allowed to start
            // background services; the foreground service fallback is handled
            // in the service code path. Log honestly.
            Log.w("LUMINA", "Could not start monitoring service from receiver", e)
        }
    }
}
