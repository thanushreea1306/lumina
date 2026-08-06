# app/services/community_alerts.py
from typing import List, Dict
from datetime import datetime
import json

class CommunityAlerts:
    """Community alert system for scam warnings"""
    
    def __init__(self):
        self.alerts = []
        self.alert_subscribers = []
    
    def create_alert(self, scam_type: str, description: str, severity: str, location: str) -> Dict:
        """Create a new community alert"""
        alert = {
            "id": f"ALT-{datetime.now().strftime('%Y%m%d')}-{len(self.alerts) + 1:04d}",
            "scam_type": scam_type,
            "description": description,
            "severity": severity,  # critical, high, medium
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "reported_by": "community",
            "actions_taken": []
        }
        self.alerts.append(alert)
        return alert
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        return self.alerts
    
    def get_alerts_by_location(self, location: str) -> List[Dict]:
        """Get alerts for a specific location"""
        return [a for a in self.alerts if location.lower() in a["location"].lower()]
    
    def subscribe_to_alerts(self, phone: str, location: str) -> Dict:
        """Subscribe a user to community alerts"""
        subscriber = {
            "phone": phone,
            "location": location,
            "subscribed_at": datetime.now().isoformat()
        }
        self.alert_subscribers.append(subscriber)
        return {"status": "subscribed", "phone": phone, "location": location}
    
    def generate_alert_message(self, alert: Dict) -> str:
        """Generate a readable alert message"""
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "🔶"
        }
        return f"""
{severity_emoji.get(alert['severity'], '🔵')} COMMUNITY ALERT

**Type:** {alert['scam_type']}
**Severity:** {alert['severity'].upper()}
**Location:** {alert['location']}
**Reported:** {alert['timestamp']}

**Description:**
{alert['description']}

**Actions:**
1. Stay alert in this area
2. Warn family and friends
3. If you receive such calls, report to 1930

💡 LUMINA - Illuminating the Digital Arrest Trap
"""