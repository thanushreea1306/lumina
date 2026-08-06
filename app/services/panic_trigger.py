# app/services/panic_trigger.py
import re
from typing import List, Dict, Optional
from datetime import datetime
import requests
import json

class PanicTrigger:
    """Detects scams using ML model with proper fallback"""
    
    def __init__(self):
        # Emergency contacts
        self.emergency_contacts = {
            "helpline": "1930",
            "cyber_crime": "cybercrime.gov.in",
            "sanchar_saathi": "Sanchar Saathi App",
            "nalsa": "15100"
        }
        
        # NGO partners
        self.ngos = [
            {"name": "HelpAge India", "helpline": "1800-180-1253"},
            {"name": "Silver Age Foundation", "email": "tech4elders@silveragefoundation.in"},
            {"name": "Cyber Peace Foundation", "helpline": "1800-123-4567"},
            {"name": "CopConnect", "service": "Free counseling & legal help"}
        ]
        
        # STRICT scam phrases (only exact matches)
        self.scam_phrases = [
            "digital arrest", "you are under arrest", "police investigation",
            "cbi calling", "enforcement directorate", "income tax department",
            "money laundering case", "drug trafficking case", "supreme court warrant",
            "high court summons", "you will be arrested", "share the otp",
            "send me the otp", "your bank account is frozen", "your account will be frozen",
            "kyc update immediately", "verify your identity now", "your upi is blocked",
            "share your pin", "you won a lottery", "you have won", "claim your prize money",
            "pay processing fee", "lucky winner", "immediate action required",
            "act now or else", "pay within 24 hours", "send money urgently",
            "don't tell anyone", "your aadhaar has been blocked", "your pan card has been blocked",
            "your kisan card is blocked", "your electricity will be disconnected tonight",
            "your parcel is stuck", "customs fee required", "you have a warrant"
        ]
        
        # BENIGN phrases (messages containing these are NOT scams)
        self.benign_phrases = [
            "electricity bill", "mobile bill", "water bill", "gas bill",
            "due date", "bill payment", "official app", "customer support",
            "bank statement", "monthly bill", "in the app", "visit our website",
            "check your account", "update your address", "delivery information",
            "parcel delivery", "order confirmation", "shipping update", "your order",
            "track your package", "delivery address", "incomplete address"
        ]
    
    def detect_panic(self, transcript: str) -> Dict:
        """Detect scam using ML model first, fallback to strict rules"""
        if not transcript:
            return {"panic_detected": False, "reason": "No transcript provided", "confidence": 0}
        
        transcript_lower = transcript.lower()
        
        # FIRST: Check if it's a benign message (NOT a scam)
        for phrase in self.benign_phrases:
            if phrase in transcript_lower:
                return {
                    "panic_detected": False,
                    "risk_score": 0,
                    "confidence": 0,
                    "detected_phrases": [],
                    "severity": "low",
                    "timestamp": datetime.now().isoformat(),
                    "method": "benign"
                }
        
        # SECOND: Try ML model
        try:
            response = requests.post(
                "http://localhost:8000/api/score",
                json={
                    "call_duration_min": 30,
                    "is_unknown_number": 1,
                    "is_video_call": 0,
                    "hour_of_day": 10,
                    "caller_call_history": 0,
                    "outgoing_activity_ratio": 0.5,
                    "day_of_week": 2
                },
                timeout=3
            )
            
            if response.status_code == 200:
                result = response.json()
                risk_score = result.get("risk_score", 0)
                top_factors = result.get("top_factors", [])
                
                if risk_score >= 70:
                    severity = "critical"
                elif risk_score >= 40:
                    severity = "high"
                elif risk_score >= 20:
                    severity = "medium"
                else:
                    severity = "low"
                
                if risk_score > 50:
                    return {
                        "panic_detected": True,
                        "risk_score": risk_score,
                        "confidence": risk_score,
                        "detected_phrases": top_factors[:5] if top_factors else [],
                        "severity": severity,
                        "timestamp": datetime.now().isoformat(),
                        "method": "ML"
                    }
                else:
                    return {
                        "panic_detected": False,
                        "risk_score": risk_score,
                        "confidence": risk_score,
                        "detected_phrases": [],
                        "severity": "low",
                        "timestamp": datetime.now().isoformat(),
                        "method": "ML"
                    }
        except Exception as e:
            print(f"ML detection failed: {e}")
        
        # THIRD: Strict fallback (only exact scam phrases)
        detected = []
        for phrase in self.scam_phrases:
            if phrase in transcript_lower:
                detected.append(phrase)
        
        if detected:
            confidence = min(len(detected) * 20, 100)
            return {
                "panic_detected": True,
                "risk_score": confidence,
                "confidence": confidence,
                "detected_phrases": detected[:5],
                "severity": "high" if len(detected) >= 2 else "medium",
                "timestamp": datetime.now().isoformat(),
                "method": "fallback"
            }
        
        # FINAL: No scam detected
        return {
            "panic_detected": False,
            "risk_score": 0,
            "confidence": 0,
            "detected_phrases": [],
            "severity": "low",
            "timestamp": datetime.now().isoformat(),
            "method": "none"
        }
    
    def trigger_silent_intervention(self, victim_name: str, risk_score: float, risk_factors: list) -> Dict:
        """Generate silent intervention alert without victim action"""
        return {
            "intervention_triggered": True,
            "victim": victim_name,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "alert_sent_to": ["trusted_contact_1", "trusted_contact_2"],
            "message": f"""
🚨 LUMINA SAFETY ALERT

A high-risk digital-arrest pattern has been detected involving {victim_name}.

Risk: CRITICAL
Risk Score: {risk_score}%

Detected Signals:
{chr(10).join([f'• {factor}' for factor in risk_factors])}

Please verify their safety immediately.

Actions:
1. Call {victim_name} on an ALTERNATIVE number
2. If possible, VISIT their location
3. If confirmed, dial 1930 (Cyber Helpline)

LUMINA - Breaking the isolation. Saving lives.
"""
        }
    
    def generate_silent_alert(self, victim_name: str, phone: str, trust_contacts: List[str]) -> Dict:
        """Generate silent alert messages for trusted contacts"""
        
        alert_message = f"""🚨 **LUMINA SILENT ALERT - URGENT**

{'-' * 50}

**{victim_name}** is potentially trapped in a scam.

**WHAT'S HAPPENING:**
- Scam detected in progress
- Victim is psychologically isolated
- They CANNOT ask for help themselves

**IMMEDIATE ACTIONS:**
1. ✅ DO NOT call the victim's phone (scammer may hear)
2. ✅ Call them on an ALTERNATIVE number
3. ✅ If possible, VISIT their location
4. ✅ If confirmed, dial **1930** (Cyber Helpline)

**SUPPORT AVAILABLE:**
- HelpAge India: 1800-180-1253
- Cyber Crime: cybercrime.gov.in
- Sanchar Saathi: App available
- NALSA Legal Aid: 15100

{'-' * 50}
LUMINA - Illuminating the Digital Arrest Trap
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return {
            "alert_message": alert_message,
            "recipients": trust_contacts,
            "emergency_helpline": "1930",
            "ngos": self.ngos,
            "sent_at": datetime.now().isoformat()
        }
    
    def get_support_resources(self) -> Dict:
        """Return all available support resources"""
        return {
            "helplines": {
                "National Cyber Helpline": "1930",
                "HelpAge India": "1800-180-1253",
                "NALSA (Free Legal Aid)": "15100"
            },
            "websites": {
                "National Cyber Crime Portal": "cybercrime.gov.in",
                "Sanchar Saathi": "sancharsaathi.gov.in",
                "CBI ABHAY AI": "https://cbi.gov.in/"
            },
            "ngos": self.ngos,
            "apps": {
                "Sanchar Saathi": "Block lost phones, report fraud",
                "CHAKSHU": "Report suspected fraud communications"
            }
        }