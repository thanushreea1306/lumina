# app/services/panic_trigger.py
import os
import re
from typing import List, Dict, Optional
from datetime import datetime
import json

class PanicTrigger:
    """Detects scams using a pure rule-based phrase engine"""
    
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
        
        # Scam phrase categories with severity weights (rule-based engine)
        self.risk_indicator_phrases = {
            "authority impersonation": {
                "weight": 2,
                "phrases": [
                    "cbi", "police", "enforcement directorate", "income tax department",
                    "supreme court", "high court", "customs", "cyber cell",
                    "investigating officer", "judge",
                ],
            },
            "arrest threats": {
                "weight": 3,
                "phrases": [
                    "digital arrest", "you are under arrest", "you will be arrested",
                    "arrest warrant", "court summons", "you have a warrant",
                    "taken into custody", "money laundering case", "drug trafficking case",
                ],
            },
            "urgency": {
                "weight": 1,
                "phrases": [
                    "immediate action required", "act now or else", "within 24 hours",
                    "pay within 24 hours", "urgent", "hurry", "immediately",
                    "will be disconnected tonight", "deadline", "right now",
                ],
            },
            "financial demand": {
                "weight": 3,
                "phrases": [
                    "share the otp", "send me the otp", "share your pin",
                    "your bank account is frozen", "your account will be frozen",
                    "your upi is blocked", "kyc update immediately",
                    "verify your identity now", "your aadhaar has been blocked",
                    "your pan card has been blocked", "your kisan card is blocked",
                    "send money urgently", "transfer the money", "pay a fine",
                    "customs fee required", "claim your prize money", "you won a lottery",
                    "pay processing fee", "lucky winner",
                ],
            },
            "secrecy": {
                "weight": 2,
                "phrases": [
                    "don't tell anyone", "keep this confidential",
                    "don't inform your family", "don't share this with anyone",
                    "stay on the line", "don't disconnect", "keep it a secret",
                    "don't tell your bank",
                ],
            },
        }

        # All scam phrases (union of categories) kept for compatibility
        self.scam_phrases = [
            phrase
            for cfg in self.risk_indicator_phrases.values()
            for phrase in cfg["phrases"]
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
        """Detect scam using a pure rule-based phrase analysis (NOT ML)."""
        now = datetime.now().isoformat()

        if not transcript:
            return {
                "panic_detected": False,
                "risk_score": 0,
                "confidence": 0,
                "risk_level": "low",
                "severity": "low",
                "matched_evidence": [],
                "risk_indicators": [],
                "detected_phrases": [],
                "explanation": "No transcript provided.",
                "method": "rule-based",
                "reason": "No transcript provided",
                "timestamp": now,
            }

        text = transcript.lower()

        # Match phrases per risk-indicator category
        matched_evidence = []
        matched_indicators = []
        total_weight = 0
        for indicator, cfg in self.risk_indicator_phrases.items():
            hits = [phrase for phrase in cfg["phrases"] if phrase in text]
            if hits:
                matched_indicators.append(indicator)
                total_weight += cfg["weight"]
                matched_evidence.extend(hits)

        # Deterministic score from indicator weights + evidence count
        risk_score = min(100, total_weight * 10 + len(matched_evidence) * 5)

        if risk_score >= 70:
            risk_level = "critical"
        elif risk_score >= 45:
            risk_level = "high"
        elif risk_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        panic_detected = risk_level in ("medium", "high", "critical")

        # Build a human-readable explanation
        benign_hits = [phrase for phrase in self.benign_phrases if phrase in text]
        if matched_indicators:
            explanation = (
                f"Detected {len(matched_indicators)} risk indicator(s) "
                f"({', '.join(matched_indicators)}) from {len(matched_evidence)} "
                f"matched phrase(s). Risk level: {risk_level}."
            )
            if benign_hits:
                explanation += (
                    f" Note: benign phrases were also present "
                    f"({', '.join(benign_hits[:3])})."
                )
        else:
            explanation = (
                "No scam indicators detected. "
                "Matched benign phrase(s): "
                f"{', '.join(benign_hits[:3]) if benign_hits else 'none'}."
            )

        return {
            "panic_detected": panic_detected,
            "risk_score": risk_score,
            "confidence": risk_score,
            "risk_level": risk_level,
            "severity": risk_level,
            "matched_evidence": matched_evidence,
            "risk_indicators": matched_indicators,
            "detected_phrases": matched_evidence[:5],
            "explanation": explanation,
            "method": "rule-based",
            "timestamp": now,
        }
    
    def trigger_silent_intervention(
        self,
        victim_name: str,
        risk_score: float,
        risk_factors: list,
        risk_level: str = "low",
    ) -> Dict:
        """Generate silent intervention alert without victim action.

        Intervention is only triggered for HIGH or CRITICAL risk. When the alert
        is built but no real delivery is configured, the result is explicitly
        marked as simulated/not delivered so no fake recipient is presented as a
        real trusted contact.
        """
        from app.services.alert import (
            _send_via_twilio,
            _trusted_contacts,
            _twilio_configured,
        )

        risk_level = str(risk_level or "low").lower()
        intervention_triggered = risk_level in ("high", "critical")

        base = {
            "intervention_triggered": intervention_triggered,
            "victim": victim_name,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
        }

        if not intervention_triggered:
            return {
                **base,
                "alert_sent_to": [],
                "delivered": False,
                "delivery_status": "NOT_TRIGGERED",
                "message": None,
                "reason": (
                    "Silent intervention only applies to HIGH or CRITICAL risk "
                    f"(current risk level: {risk_level.upper()})."
                ),
            }

        message = f"""
LUMINA SAFETY ALERT

A high-risk digital-arrest pattern has been detected involving {victim_name}.

Risk: {risk_level.upper()}
Risk Score: {risk_score}%

Detected Signals:
{chr(10).join([f'- {factor}' for factor in risk_factors])}

Please verify their safety immediately.

Actions:
1. Call {victim_name} on an ALTERNATIVE number
2. If possible, VISIT their location
3. If confirmed, dial 1930 (Cyber Helpline)

LUMINA - Breaking the isolation. Saving lives.
"""

        contacts = _trusted_contacts()
        mode = os.getenv("LUMINA_ALERT_MODE", "demo").lower()

        if not contacts:
            return {
                **base,
                "alert_sent_to": [],
                "delivered": False,
                "delivery_status": "SIMULATED",
                "message": message,
                "reason": (
                    "No trusted contacts configured (LUMINA_TRUSTED_CONTACTS); "
                    "alert built but not delivered."
                ),
            }

        if mode == "real":
            if not _twilio_configured():
                return {
                    **base,
                    "alert_sent_to": contacts,
                    "delivered": False,
                    "delivery_status": "FAILED",
                    "message": message,
                    "reason": (
                        "Real mode requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN "
                        "and TWILIO_FROM_NUMBER env vars."
                    ),
                }
            delivery_log = []
            for recipient in contacts:
                delivered, reason = _send_via_twilio(message, recipient)
                delivery_log.append(
                    {"recipient": recipient, "delivered": delivered, "reason": reason}
                )
            delivered = all(item["delivered"] for item in delivery_log)
            return {
                **base,
                "alert_sent_to": contacts,
                "delivered": delivered,
                "delivery_status": "SENT" if delivered else "FAILED",
                "delivery_log": delivery_log,
                "message": message,
            }

        return {
            **base,
            "alert_sent_to": contacts,
            "delivered": False,
            "delivery_status": "SIMULATED",
            "message": message,
            "reason": "Demo mode - alert built but not delivered (simulated).",
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