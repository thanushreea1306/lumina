package com.lumina.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import android.util.Log

class CallReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == TelephonyManager.ACTION_PHONE_STATE_CHANGED) {
            val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE)
            val phoneNumber = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)

            when (state) {
                TelephonyManager.EXTRA_STATE_RINGING -> {
                    Log.d("LUMINA", "📞 Incoming call from: $phoneNumber")
                }
                TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                    Log.d("LUMINA", "📞 Call started")
                }
                TelephonyManager.EXTRA_STATE_IDLE -> {
                    Log.d("LUMINA", "📞 Call ended")
                }
            }
        }
    }
}