# app/services/android_simulator.py
import random
from datetime import datetime
from app.services.isolation_detector import DeviceTelemetry, IsolationDetector

class AndroidDeviceSimulator:
    """Simulates Android device telemetry for testing"""
    
    def __init__(self):
        self.detector = IsolationDetector()
    
    def generate_scam_scenario(self, duration_minutes: int = 180) -> DeviceTelemetry:
        """Generate telemetry for a digital arrest scam scenario"""
        return DeviceTelemetry(
            call_duration_minutes=duration_minutes,
            is_unknown_number=True,
            is_video_call=True,
            screen_time_on_call_percent=random.randint(85, 98),
            num_app_switches=random.randint(0, 2),
            num_home_presses=random.randint(0, 1),
            has_sms_activity=False,
            has_social_app_activity=False,
            location_change=random.randint(0, 30),
            screen_brightness=random.randint(85, 100),
            screen_on_continuous_hours=random.randint(4, 8)
        )
    
    def generate_normal_scenario(self) -> DeviceTelemetry:
        """Generate telemetry for a normal call"""
        return DeviceTelemetry(
            call_duration_minutes=random.randint(2, 15),
            is_unknown_number=random.choice([True, False]),
            is_video_call=random.choice([True, False]),
            screen_time_on_call_percent=random.randint(20, 50),
            num_app_switches=random.randint(5, 20),
            num_home_presses=random.randint(5, 15),
            has_sms_activity=True,
            has_social_app_activity=True,
            location_change=random.randint(100, 500),
            screen_brightness=random.randint(30, 60),
            screen_on_continuous_hours=random.randint(0, 2)
        )
    
    def run_demo(self):
        """Run a complete demo of the system"""
        print("="*60)
        print("[RUN] LUMINA ISOLATION DETECTION DEMO")
        print("="*60)
        
        # High-risk scam scenario
        print("\n[TEL] SCENARIO 1: Digital Arrest Scam (180 minutes)")
        scam_telemetry = self.generate_scam_scenario(180)
        scam_result = self.detector.detect(scam_telemetry)
        
        print(f"Isolation Score: {scam_result['isolation_score']}%")
        print(f"Risk Level: {scam_result['risk_level']}")
        print(f"Risk Factors: {', '.join(scam_result['risk_factors'])}")
        
        if scam_result['alert_triggered']:
            print("\n[ALERT] ALERT TRIGGERED! Family will be notified.")
            alert = self.detector.generate_alert_message(
                victim_name="Family Member",
                score=scam_result['isolation_score'],
                factors=scam_result['risk_factors']
            )
            print(alert.replace("\U0001F6A8", "[ALERT]").replace("\U00002705", "[OK]"))
        
        # Normal call scenario
        print("\n" + "-"*60)
        print("\n[TEL] SCENARIO 2: Normal Call (5 minutes)")
        normal_telemetry = self.generate_normal_scenario()
        normal_result = self.detector.detect(normal_telemetry)
        
        print(f"Isolation Score: {normal_result['isolation_score']}%")
        print(f"Risk Level: {normal_result['risk_level']}")
        
        if not normal_result['alert_triggered']:
            print("[OK] No alert triggered (normal behavior)")
        
        print("\n" + "="*60)
        print("[OK] Demo Complete!")
        print("""
        [TIP] LUMINA evaluates simulated phone telemetry through the backend
        risk engine. Real on-device capture on the victim's phone is future
        work (the Android app is currently a skeleton).
        """)

if __name__ == "__main__":
    simulator = AndroidDeviceSimulator()
    simulator.run_demo()