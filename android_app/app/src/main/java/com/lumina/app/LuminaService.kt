package com.lumina.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * Foreground service that holds the real call-lifecycle capture for as long as
 * the user has monitoring active.
 *
 * Phase 2: captured call events locally only.
 * Phase 4A: creates a backend session when monitoring starts and syncs
 * completed call events to the backend via [SyncManager].
 *
 * Truthful by design:
 *  - Owns a [LocalEventStore], [CallMonitor], and [SyncManager].
 *  - Completed calls are recorded on-device first; upload happens only
 *    when consent exists and a real backend endpoint is configured.
 *  - No fabricated data, no location telemetry, no automatic upload of
 *    events that were not genuinely observed.
 */
class LuminaService : Service() {

    private lateinit var store: LocalEventStore
    private lateinit var secretStore: SecretStore
    private lateinit var transport: LuminaTransport
    private lateinit var syncManager: SyncManager
    private lateinit var observationManager: ObservationManager
    private lateinit var decisionFetcher: DecisionFetcher
    private lateinit var userResponseSender: UserResponseSender
    private var monitor: CallMonitor? = null

    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "lumina_call_channel"
        private const val TAG = "LUMINA.Service"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        if (!LuminaConfig.hasUserConsent(this)) {
            Log.w(TAG, "Refusing to monitor: no user consent")
            stopSelf()
            return
        }

        store = LocalEventStore(this)
        store.setConsent(true)

        // Secure credential storage (Android Keystore-backed encryption)
        secretStore = KeystoreSecretStore(this)

        // Register device in background (non-blocking)
        Thread {
            ensureDeviceRegistered()
        }.start()

        transport = HttpsLuminaTransport(
            configuredEndpoint = { LuminaConfig.backendEndpoint(this) },
            isAllowedToSend = { LuminaConfig.hasUserConsent(this) },
            secretStore = secretStore,
        )

        syncManager = SyncManager(store, transport)
        observationManager = ObservationManager(store, transport)
        decisionFetcher = DecisionFetcher(transport)
        userResponseSender = UserResponseSender(transport)

        // Trigger an initial sync attempt (e.g. after service restart
        // with pending events and observations from a previous run).
        syncManager.requestSync()
        observationManager.requestSync()

        monitor = CallMonitor(
            appContext = this,
            store = store,
            onEventCaptured = { _ ->
                // A completed call was captured; attempt to sync it.
                syncManager.requestSync()
            },
        ).also { it.start() }

        startForeground(
            NOTIFICATION_ID,
            buildNotification("LUMINA Active", "Monitoring calls")
        )
        Log.d(TAG, "Service created; monitoring started")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int =
        START_STICKY

    override fun onDestroy() {
        monitor?.stop()
        monitor = null
        // NOTE: We do NOT set consent to false here. Service destruction
        // (by the OS for lifecycle/resource reasons) is not the same as
        // the user explicitly revoking consent. Consent state is managed
        // by LuminaConfig (the source of truth) and checked via
        // LuminaConfig.hasUserConsent() in onCreate() and in the
        // transport's isAllowedToSend lambda. If the user revoked consent,
        // LuminaConfig reflects that; if the OS destroyed the service,
        // consent remains whatever the user configured.
        super.onDestroy()
    }

    private fun buildNotification(title: String, content: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "LUMINA Call Monitoring",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows that LUMINA is capturing call lifecycle"
            }
            getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }

    /**
     * Register device with backend if not already registered.
     * This is a one-time operation; credentials are stored securely.
     */
    private fun ensureDeviceRegistered() {
        if (secretStore.hasCredentials()) {
            Log.d(TAG, "Device already registered: ${secretStore.getDeviceId()}")
            return
        }

        val endpoint = LuminaConfig.backendEndpoint(this)
        if (!endpoint.lowercase().startsWith("https://") ||
            endpoint.contains("example.invalid", ignoreCase = true)) {
            Log.w(TAG, "Backend not configured; device registration deferred")
            return
        }

        Log.d(TAG, "Registering device with backend...")
        val result = DeviceAuth.registerDevice(endpoint)
        when (result) {
            is RegistrationResult.Success -> {
                secretStore.saveCredentials(result.deviceId, result.deviceSecret)
                Log.d(TAG, "Device registered: ${result.deviceId}")
            }
            is RegistrationResult.Failed -> {
                Log.e(TAG, "Device registration failed: ${result.detail}")
                // Events will remain pending; sync will fail with auth error
                // until registration succeeds.
            }
        }
    }

    /** Expose managers for Activity access. */
    fun getObservationManager(): ObservationManager = observationManager
    fun getDecisionFetcher(): DecisionFetcher = decisionFetcher
    fun getUserResponseSender(): UserResponseSender = userResponseSender
    fun getStore(): LocalEventStore = store
    fun getSecretStore(): SecretStore = secretStore

    override fun onBind(intent: Intent?): IBinder? = null
}
