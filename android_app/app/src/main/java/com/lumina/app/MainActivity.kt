package com.lumina.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var riskScoreText: TextView
    private lateinit var startButton: Button
    private lateinit var testButton: Button

    companion object {
        private const val PERMISSION_REQUEST_CODE = 100
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize views
        statusText = findViewById(R.id.statusText)
        riskScoreText = findViewById(R.id.riskScoreText)
        startButton = findViewById(R.id.startButton)
        testButton = findViewById(R.id.testButton)

        // Check permissions
        checkAndRequestPermissions()

        // Start service button
        startButton.setOnClickListener {
            startLuminaService()
        }

        // Test button
        testButton.setOnClickListener {
            simulateScamCall()
        }

        // Update status
        updateStatus()
    }

    private fun checkAndRequestPermissions() {
        val permissions = mutableListOf<String>()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.READ_PHONE_STATE)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            if (!checkUsageStatsPermission()) {
                Toast.makeText(this, "Please enable usage access", Toast.LENGTH_LONG).show()
                val intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
                startActivity(intent)
            }
        }

        if (permissions.isNotEmpty()) {
            ActivityCompat.requestPermissions(
                this,
                permissions.toTypedArray(),
                PERMISSION_REQUEST_CODE
            )
        }
    }

    private fun checkUsageStatsPermission(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            val usageStatsManager = getSystemService(USAGE_STATS_SERVICE) as android.app.usage.UsageStatsManager
            val currentTime = System.currentTimeMillis()
            val stats = usageStatsManager.queryUsageStats(
                android.app.usage.UsageStatsManager.INTERVAL_DAILY,
                currentTime - 1000 * 60 * 60 * 24,
                currentTime
            )
            return stats != null && stats.isNotEmpty()
        }
        return true
    }

    private fun startLuminaService() {
        val serviceIntent = Intent(this, LuminaService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
        statusText.text = "🟢 LUMINA Active - Monitoring"
        Toast.makeText(this, "LUMINA Service Started", Toast.LENGTH_SHORT).show()
    }

    private fun simulateScamCall() {
        Toast.makeText(this, "📞 Simulating Scam Call...", Toast.LENGTH_SHORT).show()
        riskScoreText.text = "Risk: 94% - CRITICAL"
        statusText.text = "🚨 SCAM DETECTED! Alerting family..."
        
        sendAlertToAPI()
    }

    private fun sendAlertToAPI() {
        Thread {
            try {
                // For real Android device, use your computer's IP
                // For emulator, use 10.0.2.2
                val url = "http://10.0.2.2:8000/api/detect-isolation"
                
                val json = """
                {
                    "call_duration_minutes": 180,
                    "is_unknown_number": true,
                    "is_video_call": true,
                    "screen_time_on_call_percent": 95,
                    "num_app_switches": 0,
                    "num_home_presses": 0,
                    "has_sms_activity": false,
                    "has_social_app_activity": false,
                    "location_change": 10,
                    "screen_brightness": 90,
                    "screen_on_continuous_hours": 6
                }
                """.trimIndent()

                val connection = java.net.URL(url).openConnection() as java.net.HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true

                connection.outputStream.write(json.toByteArray())
                connection.outputStream.flush()

                val responseCode = connection.responseCode
                if (responseCode == 200) {
                    runOnUiThread {
                        Toast.makeText(this, "✅ Alert sent to family!", Toast.LENGTH_LONG).show()
                        statusText.text = "✅ Alert sent - Family notified"
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    Toast.makeText(this, "❌ Error: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun updateStatus() {
        statusText.text = "🟡 LUMINA Ready"
        riskScoreText.text = "Risk: 0% - Monitoring"
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            if (grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                Toast.makeText(this, "✅ Permissions granted", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "⚠️ Some permissions denied", Toast.LENGTH_LONG).show()
            }
        }
    }
}