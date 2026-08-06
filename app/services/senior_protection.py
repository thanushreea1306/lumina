# app/services/senior_protection.py
from typing import List, Dict

class SeniorProtection:
    """Senior citizen protection module with NGO and government integration"""
    
    def __init__(self):
        # Partner NGOs focused on elderly protection
        self.partner_ngos = [
            {
                "name": "HelpAge India",
                "helpline": "1800-180-1253",
                "services": ["Elderly support", "Counseling", "Legal aid"],
                "website": "https://www.helpageindia.org/"
            },
            {
                "name": "Silver Age Foundation",
                "contact": "tech4elders@silveragefoundation.in",
                "services": ["Digital literacy", "Fraud awareness"],
                "website": "https://silveragefoundation.in/"
            },
            {
                "name": "Cyber Peace Foundation",
                "helpline": "1800-123-4567",
                "services": ["Cyber awareness", "Victim support"],
                "website": "https://cyberpeace.org/"
            },
            {
                "name": "CopConnect",
                "services": ["Free counseling", "Legal assistance", "Help with complaints"],
                "note": "Bridges gap between victims and law enforcement"
            }
        ]
        
        # Government resources
        self.government_resources = {
            "I4C": {
                "name": "Indian Cyber Crime Coordination Centre",
                "website": "cybercrime.gov.in",
                "helpline": "1930"
            },
            "Sanchar Saathi": {
                "name": "Sanchar Saathi",
                "description": "Block lost/stolen phones, report fraud",
                "downloads": "1.4 crore+",
                "blocked_devices": "42 lakh+",
                "app": "Available on Play Store"
            },
            "CHAKSHU": {
                "name": "CHAKSHU",
                "description": "Report suspected fraud communications",
                "actions": "40.96 lakh+ actions taken"
            },
            "NALSA": {
                "name": "National Legal Services Authority",
                "helpline": "15100",
                "service": "Free legal aid"
            }
        }
    
    def get_ngo_list(self) -> List[Dict]:
        """Return list of partner NGOs"""
        return self.partner_ngos
    
    def get_government_resources(self) -> Dict:
        """Return government resources"""
        return self.government_resources
    
    def generate_awareness_material(self) -> str:
        """Generate educational material for NGO workshops"""
        return """
🚨 **DIGITAL ARREST SCAMS: KNOW YOUR RIGHTS**

**What is a Digital Arrest?**
There is NO concept of 'digital arrest' in Indian law. No government agency:
- Arrests over video calls
- Demands payment over phone
- Asks for OTP, PIN, or password

**What to do if you receive such a call:**
1. HANG UP immediately
2. DO NOT share any personal information
3. Call 1930 to report
4. Visit cybercrime.gov.in
5. Tell family members

**Share this information with your community!**

💡 LUMINA - Illuminating the Digital Arrest Trap
    Helpline: 1930
    Website: cybercrime.gov.in
"""
    
    def get_senior_support_guide(self) -> Dict:
        """Return a guide for senior citizens"""
        return {
            "title": "Digital Safety Guide for Senior Citizens",
            "sections": [
                {
                    "heading": "1. Never Share Personal Information",
                    "content": "No government agency asks for OTP, PIN, or password over phone."
                },
                {
                    "heading": "2. Verify Before Acting",
                    "content": "If someone claims to be from a government agency, hang up and call the official number."
                },
                {
                    "heading": "3. Don't Panic",
                    "content": "Scammers create fear. Take a moment to breathe and think."
                },
                {
                    "heading": "4. Tell Someone",
                    "content": "Always tell a family member or trusted friend about suspicious calls."
                },
                {
                    "heading": "5. Report Immediately",
                    "content": "Dial 1930 or visit cybercrime.gov.in to report scams."
                }
            ],
            "emergency_contacts": {
                "National Cyber Helpline": "1930",
                "HelpAge India": "1800-180-1253",
                "NALSA": "15100"
            }
        }