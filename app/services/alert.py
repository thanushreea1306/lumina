# app/services/alert.py
from datetime import datetime

def send_family_alert(elder_name: str, risk_level: str, duration: float, features: dict):
    """Generate a family alert message for a high-risk call"""
    
    risk_emoji = {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "🟡",
        "low": "✅"
    }
    
    message = f"""
{risk_emoji.get(risk_level, '🔵')} LUMINA FAMILY ALERT

{elder_name} has been on a suspicious call for {duration:.0f} minutes.
Risk Level: {risk_level.upper()}

Call Details:
- Duration: {duration:.0f} minutes
- Unknown Number: {'Yes' if features.get('is_unknown_number', 0) else 'No'}
- Video Call: {'Yes' if features.get('is_video_call', 0) else 'No'}
- Time: {features.get('hour_of_day', 0)}:00

This matches known digital arrest scam patterns.

RECOMMENDED ACTIONS:
1. ✅ Call {elder_name} on another line immediately
2. ✅ Visit their home if possible
3. ✅ If confirmed scam, dial 1930 (National Cyber Helpline)
4. ✅ Report at cybercrime.gov.in

{risk_level.upper()} RISK: Do not ignore this alert!

LUMINA - Illuminating the Digital Arrest Trap
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    return message