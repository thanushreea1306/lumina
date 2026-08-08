# app/services/isolation_detector.py
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class DeviceTelemetry:
    """Device telemetry data from Android phone"""
    call_duration_minutes: float
    is_unknown_number: bool
    is_video_call: bool
    screen_time_on_call_percent: float
    num_app_switches: int
    num_home_presses: int
    has_sms_activity: bool
    has_social_app_activity: bool
    location_change: float
    screen_brightness: float
    screen_on_continuous_hours: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class IsolationDetector:
    """Detects if a victim is trapped in a digital arrest scam"""
    
    def __init__(self):
        self.isolation_threshold = 75
        self.weights = {
            'call_duration': 0.25,
            'unknown_number': 0.10,
            'video_call': 0.05,
            'screen_time_on_call': 0.20,
            'no_app_switches': 0.15,
            'no_home_presses': 0.10,
            'no_sms_activity': 0.05,
            'no_social_activity': 0.05,
            'static_location': 0.03,
            'high_brightness': 0.02
        }
    
    def calculate_isolation_score(self, telemetry: DeviceTelemetry) -> Dict:
        """Calculate isolation risk score (0-100)"""
        score = 0
        factors = []
        
        # 1. Call Duration
        if telemetry.call_duration_minutes > 60:
            score += self.weights['call_duration'] * 100
            factors.append(f"Long call duration ({int(telemetry.call_duration_minutes)} min)")
        elif telemetry.call_duration_minutes > 30:
            score += self.weights['call_duration'] * 60
            factors.append("Medium call duration")
        
        # 2. Unknown Number
        if telemetry.is_unknown_number:
            score += self.weights['unknown_number'] * 100
            factors.append("Unknown caller")
        
        # 3. Video Call
        if telemetry.is_video_call:
            score += self.weights['video_call'] * 100
            factors.append("Video call (intimidation tactic)")
        
        # 4. Screen Time on Call
        if telemetry.screen_time_on_call_percent > 80:
            score += self.weights['screen_time_on_call'] * 100
            factors.append(f"Isolated on call ({int(telemetry.screen_time_on_call_percent)}% screen time)")
        elif telemetry.screen_time_on_call_percent > 50:
            score += self.weights['screen_time_on_call'] * 60
            factors.append("High screen time on call")
        
        # 5. No App Switches
        if telemetry.num_app_switches < 2:
            score += self.weights['no_app_switches'] * 100
            factors.append("No app switching (trapped behavior)")
        
        # 6. No Home Presses
        if telemetry.num_home_presses < 2:
            score += self.weights['no_home_presses'] * 100
            factors.append("No home button presses (frozen)")
        
        # 7. No SMS Activity
        if not telemetry.has_sms_activity:
            score += self.weights['no_sms_activity'] * 100
            factors.append("No outgoing SMS (isolation signal)")
        
        # 8. No Social App Activity
        if not telemetry.has_social_app_activity:
            score += self.weights['no_social_activity'] * 100
            factors.append("No social app activity (silenced)")
        
        # 9. Static Location
        if telemetry.location_change < 50:
            score += self.weights['static_location'] * 100
            factors.append("Static location (not moving)")
        
        # 10. High Screen Brightness
        if telemetry.screen_brightness > 80:
            score += self.weights['high_brightness'] * 100
            factors.append("High screen brightness (hyper-vigilant)")
        
        score = min(score, 100)
        
        if score >= 75:
            risk_level = "CRITICAL"
        elif score >= 50:
            risk_level = "HIGH"
        elif score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "isolation_score": round(score, 1),
            "risk_level": risk_level,
            "risk_factors": factors[:5],
            "total_factors": len(factors),
            "alert_triggered": score >= self.isolation_threshold
        }
    
    def detect(self, telemetry: DeviceTelemetry) -> Dict:
        """Main detection method"""
        return self.calculate_isolation_score(telemetry)
    
    def generate_alert_message(self, victim_name: str, score: float, factors: List[str]) -> str:
        """Generate alert message"""
        return f"""
🚨 LUMINA SAFETY ALERT - URGENT!

{'-' * 50}

{victim_name} is showing signs of being trapped in a digital arrest scam.

Isolation Risk Score: {score}%
Risk Level: CRITICAL

Detected Signals:
{chr(10).join([f'• {f}' for f in factors[:5]])}

Recommended Actions:
1. ✅ Call {victim_name} on an ALTERNATIVE number
2. ✅ If possible, VISIT their location
3. ✅ If confirmed, dial 1930 (Cyber Helpline)

LUMINA - Breaking the isolation. Saving lives.
"""