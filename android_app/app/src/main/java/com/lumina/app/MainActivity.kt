package com.lumina.app

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.material.chip.ChipGroup

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var syncStatusText: TextView
    private lateinit var consentButton: Button
    private lateinit var endpointInput: EditText
    private lateinit var saveEndpointButton: Button
    private lateinit var startButton: Button
    private lateinit var observationChipGroup: ChipGroup
    private lateinit var observationNotes: EditText
    private lateinit var submitObservationButton: Button
    private lateinit var observationStatusText: TextView
    private lateinit var decisionStateText: TextView
    private lateinit var decisionReasonText: TextView
    private lateinit var decisionActionText: TextView
    private lateinit var decisionMissingText: TextView
    private lateinit var refreshDecisionButton: Button
    private lateinit var responseDeclinedButton: Button
    private lateinit var responsePausedButton: Button
    private lateinit var responsePerformedButton: Button
    private lateinit var responseStatusText: TextView

    private var luminaService: LuminaService? = null
    private var isBound = false
    private var currentSessionId: String? = null

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            // LuminaService doesn't use a binder yet; access via static reference
            isBound = true
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            luminaService = null
            isBound = false
        }
    }

    companion object {
        private const val PERMISSION_REQUEST_CODE = 100
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        syncStatusText = findViewById(R.id.syncStatusText)
        consentButton = findViewById(R.id.consentButton)
        endpointInput = findViewById(R.id.endpointInput)
        saveEndpointButton = findViewById(R.id.saveEndpointButton)
        startButton = findViewById(R.id.startButton)
        observationChipGroup = findViewById(R.id.observationChipGroup)
        observationNotes = findViewById(R.id.observationNotes)
        submitObservationButton = findViewById(R.id.submitObservationButton)
        observationStatusText = findViewById(R.id.observationStatusText)
        decisionStateText = findViewById(R.id.decisionStateText)
        decisionReasonText = findViewById(R.id.decisionReasonText)
        decisionActionText = findViewById(R.id.decisionActionText)
        decisionMissingText = findViewById(R.id.decisionMissingText)
        refreshDecisionButton = findViewById(R.id.refreshDecisionButton)
        responseDeclinedButton = findViewById(R.id.responseDeclinedButton)
        responsePausedButton = findViewById(R.id.responsePausedButton)
        responsePerformedButton = findViewById(R.id.responsePerformedButton)
        responseStatusText = findViewById(R.id.responseStatusText)

        endpointInput.setText(LuminaConfig.backendEndpoint(this).ifPlaceholder("").toString())

        // Consent
        consentButton.setOnClickListener {
            LuminaConfig.setUserConsent(this, true)
            requestLegacyRuntimePermissions()
            Toast.makeText(this, "Consent recorded", Toast.LENGTH_SHORT).show()
            updateUI()
        }

        // Save endpoint
        saveEndpointButton.setOnClickListener {
            val ok = LuminaConfig.setBackendEndpoint(this, endpointInput.text.toString())
            Toast.makeText(
                this,
                if (ok) "Endpoint saved" else "Endpoint must be https:// and non-empty",
                Toast.LENGTH_LONG
            ).show()
        }

        // Start monitoring
        startButton.setOnClickListener {
            startLuminaService()
        }

        // Observation chip selection
        observationChipGroup.setOnCheckedStateChangeListener { _, _ ->
            val anyChecked = observationChipGroup.checkedChipIds.isNotEmpty()
            submitObservationButton.isEnabled = anyChecked
        }

        // Submit observation
        submitObservationButton.setOnClickListener {
            submitObservation()
        }

        // Refresh decision
        refreshDecisionButton.setOnClickListener {
            fetchDecision()
        }

        // User responses
        responseDeclinedButton.setOnClickListener { sendResponse("declined") }
        responsePausedButton.setOnClickListener { sendResponse("paused") }
        responsePerformedButton.setOnClickListener { sendResponse("performed") }

        updateUI()
    }

    override fun onResume() {
        super.onResume()
        updateUI()
    }

    private fun startLuminaService() {
        if (!LuminaConfig.hasUserConsent(this)) {
            Toast.makeText(this, "Consent required before monitoring starts", Toast.LENGTH_LONG).show()
            updateUI()
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Phone-state permission required to capture calls", Toast.LENGTH_LONG).show()
            return
        }
        val serviceIntent = Intent(this, LuminaService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
        bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE)

        // Get session ID from store
        val store = LocalEventStore(this)
        currentSessionId = store.getSessionId()

        observationStatusText.text = ""
        decisionStateText.text = getString(R.string.decision_loading)
        decisionReasonText.text = ""
        decisionActionText.text = ""
        decisionMissingText.text = ""

        // Enable response buttons if we have a session
        updateResponseButtons(true)

        Toast.makeText(this, "LUMINA monitoring started", Toast.LENGTH_SHORT).show()
        updateUI()
    }

    private fun submitObservation() {
        val sessionId = currentSessionId ?: run {
            Toast.makeText(this, "No active session. Start monitoring first.", Toast.LENGTH_LONG).show()
            return
        }

        val checkedIds = observationChipGroup.checkedChipIds
        if (checkedIds.isEmpty()) return

        // Map chip IDs to observation types
        val typeMap = mapOf(
            R.id.chip_authority_claim to UserObservationType.AUTHORITY_CLAIM,
            R.id.chip_threat_arrest to UserObservationType.THREAT_OF_ARREST,
            R.id.chip_threat_legal to UserObservationType.THREAT_OF_LEGAL_ACTION,
            R.id.chip_urgency to UserObservationType.URGENCY,
            R.id.chip_secrecy to UserObservationType.SECRECY_REQUEST,
            R.id.chip_money to UserObservationType.MONEY_REQUEST,
            R.id.chip_otp to UserObservationType.OTP_REQUEST,
            R.id.chip_password to UserObservationType.PASSWORD_REQUEST,
            R.id.chip_id_doc to UserObservationType.IDENTITY_DOCUMENT_REQUEST,
            R.id.chip_remote_access to UserObservationType.REMOTE_ACCESS_REQUEST,
            R.id.chip_app_install to UserObservationType.APP_INSTALL_REQUEST,
            R.id.chip_bank_transfer to UserObservationType.BANK_TRANSFER_REQUEST,
            R.id.chip_crypto to UserObservationType.CRYPTO_REQUEST,
            R.id.chip_gift_card to UserObservationType.GIFT_CARD_REQUEST,
            R.id.chip_call_back to UserObservationType.CALL_BACK_INSTRUCTION,
            R.id.chip_verification_blocked to UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED,
        )

        val notes = observationNotes.text?.toString()?.trim()?.ifEmpty { null }

        // Create observations in a local store (not service-bound for now)
        val store = LocalEventStore(this)
        val secretStore = KeystoreSecretStore(this)
        val transport = HttpsLuminaTransport(
            configuredEndpoint = { LuminaConfig.backendEndpoint(this) },
            isAllowedToSend = { LuminaConfig.hasUserConsent(this) },
            secretStore = secretStore,
        )
        val observationManager = ObservationManager(store, transport)

        var count = 0
        for (chipId in checkedIds) {
            val type = typeMap[chipId] ?: continue
            observationManager.createObservation(sessionId, type, notes)
            count++
        }

        // Attempt to sync
        observationManager.requestSync()

        // Clear selections
        observationChipGroup.clearCheck()
        observationNotes.text?.clear()
        submitObservationButton.isEnabled = false

        observationStatusText.text = "$count observation(s) saved locally — syncing when possible"
        Toast.makeText(this, getString(R.string.observation_saved), Toast.LENGTH_SHORT).show()
    }

    private fun fetchDecision() {
        val sessionId = currentSessionId ?: run {
            decisionStateText.text = getString(R.string.decision_no_session)
            return
        }

        decisionStateText.text = getString(R.string.decision_loading)
        decisionReasonText.text = ""
        decisionActionText.text = ""
        decisionMissingText.text = ""

        val secretStore = KeystoreSecretStore(this)
        val transport = HttpsLuminaTransport(
            configuredEndpoint = { LuminaConfig.backendEndpoint(this) },
            isAllowedToSend = { LuminaConfig.hasUserConsent(this) },
            secretStore = secretStore,
        )
        val fetcher = DecisionFetcher(transport)

        fetcher.fetchDecision(sessionId) { result ->
            runOnUiThread {
                when (result) {
                    is DecisionResult.Available -> displayDecision(result.decisionJson)
                    is DecisionResult.Unavailable -> {
                        decisionStateText.text = getString(R.string.decision_unavailable)
                        decisionReasonText.text = result.reason
                        decisionActionText.text = ""
                        decisionMissingText.text = ""
                    }
                }
            }
        }
    }

    private fun displayDecision(json: org.json.JSONObject) {
        val decision = json.optJSONObject("decision") ?: return
        val state = decision.optString("state", "UNKNOWN")
        val stateLabel = decision.optString("state_label", state)
        val reasonCodes = decision.optJSONArray("reason_codes") ?: org.json.JSONArray()
        val recommendedAction = decision.optString("recommended_action", "")
        val missingInfo = decision.optJSONArray("missing_information") ?: org.json.JSONArray()
        val uncertainty = decision.optJSONArray("uncertainty") ?: org.json.JSONArray()

        // State with plain-language description
        val stateDesc = when (state) {
            "CLEAR" -> getString(R.string.state_CLEAR)
            "WATCH" -> getString(R.string.state_WATCH)
            "PAUSE" -> getString(R.string.state_PAUSE)
            "VERIFY" -> getString(R.string.state_VERIFY)
            "PROTECT" -> getString(R.string.state_PROTECT)
            "RECOVERY" -> getString(R.string.state_RECOVERY)
            else -> stateLabel
        }
        decisionStateText.text = "$stateLabel — $stateDesc"

        // Reason codes
        val reasons = mutableListOf<String>()
        for (i in 0 until reasonCodes.length()) {
            reasons.add(reasonCodes.getString(i))
        }
        decisionReasonText.text = if (reasons.isNotEmpty()) {
            "Reasons:\n• ${reasons.joinToString("\n• ")}"
        } else {
            ""
        }

        // Recommended action (honest, not exaggerated)
        decisionActionText.text = if (recommendedAction.isNotEmpty()) {
            "Recommended: $recommendedAction"
        } else {
            ""
        }

        // Missing information
        val missing = mutableListOf<String>()
        for (i in 0 until missingInfo.length()) {
            missing.add(missingInfo.getString(i))
        }
        for (i in 0 until uncertainty.length()) {
            val u = uncertainty.getString(i)
            if (u !in missing) missing.add(u)
        }
        decisionMissingText.text = if (missing.isNotEmpty()) {
            "Missing: ${missing.joinToString(", ")}"
        } else {
            ""
        }

        // Enable response buttons when we have a decision
        updateResponseButtons(true)
    }

    private fun sendResponse(response: String) {
        val sessionId = currentSessionId ?: return

        val secretStore = KeystoreSecretStore(this)
        val transport = HttpsLuminaTransport(
            configuredEndpoint = { LuminaConfig.backendEndpoint(this) },
            isAllowedToSend = { LuminaConfig.hasUserConsent(this) },
            secretStore = secretStore,
        )
        val sender = UserResponseSender(transport)

        // For now, we don't have a specific action to respond to.
        // The user response records what they did in general.
        // We use "user_action" as the generic action type.
        val success = sender.sendResponse(sessionId, "user_action", response)

        responseStatusText.text = if (success) {
            getString(R.string.response_sent)
        } else {
            "Response could not be sent — will retry"
        }
    }

    private fun updateResponseButtons(enabled: Boolean) {
        responseDeclinedButton.isEnabled = enabled
        responsePausedButton.isEnabled = enabled
        responsePerformedButton.isEnabled = enabled
    }

    private fun updateUI() {
        val consented = LuminaConfig.hasUserConsent(this)
        statusText.text = if (consented) {
            "Consent recorded — monitoring available"
        } else {
            "Waiting for consent"
        }

        // Get session ID
        val store = LocalEventStore(this)
        currentSessionId = store.getSessionId()

        // Sync status
        if (currentSessionId != null) {
            val pendingObs = store.getObservations(currentSessionId!!).count {
                it.syncState == SyncState.PENDING || it.syncState == SyncState.FAILED
            }
            val totalObs = store.getObservations(currentSessionId!!).size
            syncStatusText.text = when {
                totalObs == 0 -> ""
                pendingObs > 0 -> "$pendingObs of $totalObs observations pending sync"
                else -> getString(R.string.sync_complete)
            }
        } else {
            syncStatusText.text = ""
        }

        // Decision state
        if (currentSessionId == null) {
            decisionStateText.text = getString(R.string.decision_no_session)
            decisionReasonText.text = ""
            decisionActionText.text = ""
            decisionMissingText.text = ""
            updateResponseButtons(false)
        }
    }

    private fun requestLegacyRuntimePermissions() {
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.READ_PHONE_STATE)
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), PERMISSION_REQUEST_CODE)
        }
    }

    private fun String.ifPlaceholder(fallback: String): String =
        if (this == LuminaConfig.DEFAULT_ENDPOINT) fallback else this

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.isNotEmpty() &&
                grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            Toast.makeText(
                this,
                if (allGranted) "Permissions granted — start monitoring to capture"
                else "Some permissions denied; capture will be limited",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    override fun onDestroy() {
        if (isBound) {
            unbindService(serviceConnection)
            isBound = false
        }
        super.onDestroy()
    }
}
