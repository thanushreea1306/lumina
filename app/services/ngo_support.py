# app/services/ngo_support.py
from typing import List, Dict
from datetime import datetime
import json

class NGOSupport:
    """Complete NGO and elderly support system"""
    
    def __init__(self):
        self.ngos = [
            {
                "id": "help_age_india",
                "name": "HelpAge India",
                "helpline": "1800-180-1253",
                "services": ["Elderly support", "Counseling", "Legal aid", "Home visits"],
                "website": "https://www.helpageindia.org/",
                "regions": ["All India"],
                "languages": ["Hindi", "English", "Tamil", "Telugu", "Bengali"]
            },
            {
                "id": "silver_age",
                "name": "Silver Age Foundation",
                "helpline": "011-2335-5555",
                "services": ["Digital literacy", "Fraud awareness", "Workshops"],
                "website": "https://silveragefoundation.in/",
                "regions": ["Delhi NCR", "Online"],
                "languages": ["Hindi", "English"]
            },
            {
                "id": "cyber_peace",
                "name": "Cyber Peace Foundation",
                "helpline": "1800-123-4567",
                "services": ["Cyber awareness", "Victim support", "Reporting assistance"],
                "website": "https://cyberpeace.org/",
                "regions": ["All India"],
                "languages": ["Hindi", "English", "Marathi"]
            },
            {
                "id": "copconnect",
                "name": "CopConnect",
                "helpline": "Available through app",
                "services": ["Free counseling", "Legal assistance", "Help with complaints"],
                "website": "https://copconnect.in/",
                "regions": ["All India"],
                "languages": ["Hindi", "English"]
            },
            {
                "id": "dignity_foundation",
                "name": "Dignity Foundation",
                "helpline": "022-2352-8888",
                "services": ["Elderly care", "Legal support", "Financial advice"],
                "website": "https://dignityfoundation.in/",
                "regions": ["Mumbai", "Pune", "Delhi"],
                "languages": ["Marathi", "Hindi", "English"]
            }
        ]
        
        self.awareness_kits = {
            "poster": self._generate_poster(),
            "flyer": self._generate_flyer(),
            "whatsapp_message": self._generate_whatsapp_message(),
            "workshop_guide": self._generate_workshop_guide()
        }
    
    def get_all_ngos(self) -> List[Dict]:
        """Return list of all NGOs"""
        return self.ngos
    
    def get_ngo_by_id(self, ngo_id: str) -> Dict:
        """Get NGO by ID"""
        for ngo in self.ngos:
            if ngo["id"] == ngo_id:
                return ngo
        return {"error": "NGO not found"}
    
    def get_ngos_by_region(self, region: str) -> List[Dict]:
        """Get NGOs available in a specific region"""
        result = []
        for ngo in self.ngos:
            if any(r.lower() == region.lower() or r.lower() == "all india" for r in ngo["regions"]):
                result.append(ngo)
        return result
    
    def get_ngos_by_service(self, service: str) -> List[Dict]:
        """Get NGOs offering a specific service"""
        result = []
        for ngo in self.ngos:
            if any(s.lower() in service.lower() for s in ngo["services"]):
                result.append(ngo)
        return result
    
    def get_awareness_kit(self) -> Dict:
        """Get complete awareness kit"""
        return self.awareness_kits
    
    def _generate_poster(self) -> str:
        """Generate awareness poster content"""
        return """
🚨 DIGITAL ARREST SCAM ALERT 🚨

Know Your Rights:
❌ There is NO concept of "digital arrest" in Indian law
❌ No government agency arrests over video call
❌ No agency demands payment over phone

What to Do:
1️⃣ HANG UP immediately
2️⃣ DO NOT share OTP/PIN/Password
3️⃣ Call 1930 to report
4️⃣ Tell family members

Share This Poster With Your Community!

💡 LUMINA - Illuminating the Digital Arrest Trap
    Helpline: 1930 | cybercrime.gov.in
"""
    
    def _generate_flyer(self) -> str:
        """Generate flyer content"""
        return """
📋 DIGITAL SAFETY FLYER

For Senior Citizens

❓ What is a Digital Arrest Scam?
Someone calls pretending to be police/CBI/ED. They say you're under investigation and must stay on video call for hours. They demand money to "settle" the case.

❓ Why It Works
They create fear and isolate you from family.

❓ How to Protect Yourself
✅ Always verify the call
✅ Hang up and call the official number
✅ Never share personal information
✅ Tell a family member immediately

❓ Where to Get Help
📞 1930 - National Cyber Helpline
📞 1800-180-1253 - HelpAge India
📞 15100 - NALSA Legal Aid

💡 LUMINA - Illuminating the Digital Arrest Trap
"""
    
    def _generate_whatsapp_message(self) -> str:
        """Generate WhatsApp awareness message"""
        return """
🚨 *DIGITAL ARREST SCAM AWARENESS* 🚨

Dear community member,

Digital arrest scams are on the rise. Scammers impersonate police, CBI, or ED officials to trap elders on video calls.

*Remember:*
• There is NO concept of "digital arrest" in Indian law
• No agency arrests over video calls
• No one demands payment over phone

*What to do if you receive such a call:*
1. Hang up immediately
2. Do not share any personal information
3. Call 1930 to report
4. Inform family members

*Share this message with elders in your family!*

💡 LUMINA - Illuminating the Digital Arrest Trap
📞 Helpline: 1930
🌐 cybercrime.gov.in
"""
    
    def _generate_workshop_guide(self) -> str:
        """Generate NGO workshop guide"""
        return """
📚 NGO WORKSHOP GUIDE

How to Conduct a Digital Safety Workshop for Elders

Workshop Agenda (2 hours)

1. Opening (10 min)
   - Welcome and introduction
   - Share statistics: ₹3,000+ crore lost to digital arrest scams

2. Understanding Digital Arrest Scams (20 min)
   - What is a digital arrest scam?
   - How scammers operate
   - Real-life examples

3. Protection Strategies (30 min)
   - How to identify a scam call
   - What to do when you receive a suspicious call
   - Creating a family communication plan

4. Reporting Mechanisms (20 min)
   - How to report to 1930
   - Using cybercrime.gov.in
   - Contacting NGOs

5. LUMINA Demonstration (20 min)
   - How LUMINA works
   - How to access LUMINA
   - Live demonstration

6. Q&A and Feedback (20 min)

Materials Needed:
- Projector
- Printed flyers
- Smartphone for demo
- LUMINA dashboard

💡 LUMINA - Illuminating the Digital Arrest Trap
"""
    
    def get_elderly_guide(self) -> Dict:
        """Get comprehensive elderly guide"""
        return {
            "title": "Digital Safety Guide for Senior Citizens",
            "sections": [
                {
                    "heading": "1. What is a Digital Arrest Scam?",
                    "content": "A scam where someone calls pretending to be police, CBI, or ED officials. They say you're under investigation and keep you on video call for hours. They demand money to \"settle\" the case."
                },
                {
                    "heading": "2. How to Recognize a Scam",
                    "content": "• Caller claims you're under arrest\n• Caller demands you stay on video call\n• Caller asks for OTP, PIN, or password\n• Caller threatens legal action\n• Caller demands money"
                },
                {
                    "heading": "3. What to Do",
                    "content": "1. HANG UP immediately\n2. DO NOT share any information\n3. Call 1930 to report\n4. Tell family members\n5. Visit cybercrime.gov.in"
                },
                {
                    "heading": "4. Emergency Contacts",
                    "content": "📞 1930 - National Cyber Helpline\n📞 1800-180-1253 - HelpAge India\n📞 15100 - NALSA Legal Aid\n📞 100 - Police"
                }
            ]
        }
    
    def submit_ngo_request(self, ngo_id: str, request_type: str, details: Dict) -> Dict:
        """Submit a request to an NGO"""
        ngo = self.get_ngo_by_id(ngo_id)
        if "error" in ngo:
            return {"status": "error", "message": "NGO not found"}
        
        return {
            "status": "submitted",
            "ngo": ngo["name"],
            "request_type": request_type,
            "details": details,
            "submitted_at": datetime.now().isoformat(),
            "tracking_id": f"REQ-{datetime.now().strftime('%Y%m%d')}-{hash(ngo_id) % 10000:04d}"
        }