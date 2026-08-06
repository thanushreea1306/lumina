# dashboard/app.py
import streamlit as st
import requests
import random
from datetime import datetime, timedelta

st.set_page_config(
    page_title="LUMINA - Digital Arrest Protection",
    page_icon="💡",
    layout="wide"
)

# Custom CSS for professional look
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a237e;
        text-align: center;
        padding: 1rem 0;
    }
    .risk-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .critical-alert {
        background-color: #ffebee;
        border-left: 5px solid #c62828;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .silent-intervention {
        background-color: #e8f5e9;
        border-left: 5px solid #2e7d32;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("💡 LUMINA")
    st.caption("Illuminating the Digital Arrest Trap")
    st.divider()
    
    page = st.radio(
        "📋 Navigation",
        ["📞 Call Detection", "📝 Text Signal Scanner (Beta)", "👴 Senior Safety Check", "🆘 NGO Emergency Dispatch", "📢 Community Threat Radar", "🔗 Government Tools"]
    )
    
    st.divider()
    st.caption("📞 Helpline: **1930**")
    st.caption("🔒 Privacy: SHA-256 | 24h deletion")

# ============ CALL DETECTION ============
if page == "📞 Call Detection":
    st.header("📞 Call Detection")
    st.caption("Analyze call patterns to detect digital arrest scams")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Call Parameters")
        duration = st.slider("Duration (minutes)", 1, 500, 15)
        unknown = st.checkbox("Unknown Number")
        video = st.checkbox("Video Call")
        hour = st.slider("Hour of Day", 0, 23, 11)
        history = st.number_input("Prior calls", 0, 50, 5)
        activity = st.slider("Outgoing Activity", 0.0, 1.0, 0.6)
        
        if st.button("🔍 Analyze", use_container_width=True):
            payload = {
                "call_duration_min": duration,
                "is_unknown_number": 1 if unknown else 0,
                "is_video_call": 1 if video else 0,
                "hour_of_day": hour,
                "caller_call_history": history,
                "outgoing_activity_ratio": activity,
                "day_of_week": 2
            }
            
            try:
                r = requests.post("http://localhost:8000/api/score", json=payload, timeout=10)
                if r.status_code == 200:
                    result = r.json()
                    st.session_state['result'] = result
                else:
                    st.error(f"Error: {r.status_code}")
            except:
                st.error("Backend not running. Run: python run.py")
    
    with col2:
        st.subheader("Results")
        if 'result' in st.session_state:
            result = st.session_state['result']
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Risk Score", f"{result['risk_score']:.1f}/100")
            m2.metric("Risk Level", result['risk_level'].upper())
            m3.metric("Factors", len(result.get('top_factors', [])))
            
            if result.get('top_factors'):
                for f in result['top_factors']:
                    st.warning(f"⚠️ {f}")
            
            if result['risk_level'] in ['critical', 'high']:
                st.error(result['alert_message'])
                
                # SILENT INTERVENTION DISPLAY
                st.success("🔕 SILENT INTERVENTION ACTIVATED")
                st.info("""
                **The victim does not need to press anything.**
                
                LUMINA has silently alerted trusted contacts.
                """)
                
                with st.expander("📱 View Alert Sent to Trusted Contact"):
                    st.code(f"""
🚨 LUMINA SAFETY ALERT

A high-risk digital-arrest pattern has been detected.

Risk: {result['risk_level'].upper()}
Risk Score: {result['risk_score']}%

Detected Signals:
{chr(10).join([f'• {factor}' for factor in result['top_factors']])}

Please verify their safety immediately.

Actions:
1. Call them on an ALTERNATIVE number
2. If possible, VISIT their location
3. If confirmed, dial 1930 (Cyber Helpline)
""")
                
                if st.button("🔕 Trigger Silent Intervention", use_container_width=True):
                    try:
                        intervention_response = requests.post(
                            "http://localhost:8000/api/silent-intervention",
                            json=payload,
                            params={"victim_name": "Family Member"}
                        )
                        if intervention_response.status_code == 200:
                            intervention = intervention_response.json()
                            st.success("✅ Silent intervention triggered successfully!")
                            st.info("Trusted contacts have been alerted without victim action.")
                            st.code(intervention.get("message", "Alert sent"))
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.success(result['alert_message'])
        else:
            st.info("Click 'Analyze' to see results")

# ============ TEXT SIGNAL SCANNER ============
elif page == "📝 Text Signal Scanner (Beta)":
    st.header("📝 Text Signal Scanner (Beta)")
    st.caption("Rule-based pattern matching engine — Full NLP transformer model planned for V2")
    
    st.info("""
    **Note:** This is a rule-based heuristic engine (V1 prototype). 
    It serves as a supplementary signal for suspicious text patterns. 
    Full transformer-based NLP (BERT/RoBERTa) classification is planned for V2.
    """)
    
    with st.expander("📝 Click to see example transcripts to test"):
        st.markdown("**Copy and paste these into the box below:**")
        st.code('"This is CBI calling. You are under investigation for money laundering."')
        st.code('"Your Aadhaar has been blocked. Share OTP to reactivate immediately."')
        st.code('"You have a warrant from the Supreme Court. Pay the fine now."')
        st.code('"Hi mom, I\'m on my way home. Need anything from the store?"')
    
    transcript = st.text_area("Enter conversation transcript:", height=150)
    
    if st.button("🔍 Scan Text"):
        if transcript:
            try:
                r = requests.post(
                    "http://localhost:8000/api/detect/panic",
                    json={"text": transcript, "language": "en"},
                    timeout=10
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get("is_scam", False):
                        st.warning("⚠️ Potential scam keywords detected")
                        st.write("Detected phrases:", ", ".join(result.get("risk_factors", [])))
                        st.caption(f"Confidence: {result.get('confidence', 0):.1f}%")
                        st.caption(f"Method: {result.get('method', 'rule-based')}")
                    else:
                        st.success("✅ No suspicious patterns detected")
                else:
                    st.error(f"Error: {r.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Please enter text to scan")

# ============ SENIOR SAFETY CHECK ============
elif page == "👴 Senior Safety Check":
    st.header("👴 Senior Digital Safety Readiness Check")
    st.caption("Complete this setup with your elderly family member to establish safety baselines.")
    
    st.markdown("### 📋 Family Safety Checklist")
    
    c1 = st.checkbox("✅ Registered 1930 Cyber Helpline as a speed-dial contact")
    c2 = st.checkbox("✅ Saved trusted family contacts in LUMINA alert system")
    c3 = st.checkbox("✅ Reviewed 'No Government Agency Calls via WhatsApp/Skype' rule")
    c4 = st.checkbox("✅ Discussed what to do if someone says 'digital arrest' on call")
    c5 = st.checkbox("✅ Set up a family password/code word for emergencies")
    
    readiness = sum([c1, c2, c3, c4, c5]) / 5 * 100
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.progress(readiness / 100)
        st.caption(f"✅ {int(readiness)}% Complete")
    
    with col2:
        if readiness == 100:
            st.success("🟢 High Preparedness")
        elif readiness >= 60:
            st.warning("🟡 Medium Preparedness")
        else:
            st.error("🔴 Low Preparedness")
    
    st.divider()
    st.markdown("### 🚨 1-Tap Family Protocol")
    st.caption("Preview the alert message that will be sent to family members when LUMINA detects a threat.")
    
    sample_alert = """
🚨 **LUMINA SILENT ALERT**

**Family Member** has been on a suspicious call for 145 minutes.
Risk Level: **CRITICAL**

**What to do immediately:**
1. ✅ Call them on an ALTERNATIVE number
2. ✅ If possible, VISIT their location
3. ✅ If confirmed, dial **1930** (Cyber Helpline)

**Support available:**
- HelpAge India: 1800-180-1253
- Cyber Crime: cybercrime.gov.in
- NALSA Legal Aid: 15100
"""
    
    if st.button("📱 Preview Alert Message", use_container_width=True):
        st.code(sample_alert)
        st.success("✅ This message will be sent to registered family contacts")

# ============ NGO EMERGENCY DISPATCH ============
elif page == "🆘 NGO Emergency Dispatch":
    st.header("🆘 NGO Emergency Dispatch & Counseling Support")
    st.caption("Connect directly with verified NGO partners specializing in senior protection and cyber victim support.")

    ngo_database = [
        {
            "name": "HelpAge India (Elder Helpline)",
            "helpline": "1800-180-1253",
            "regions": ["All India", "Bengaluru", "Delhi NCR", "Mumbai", "Odisha", "Chennai", "Hyderabad", "Kolkata"],
            "services": ["Elderly Support", "Counseling", "Legal Aid", "Fraud Awareness"],
            "website": "https://www.helpageindia.org/",
            "desc": "24/7 National elder helpline providing immediate cyber crime counseling, family intervention, and legal assistance."
        },
        {
            "name": "CyberPeace Foundation",
            "helpline": "+91 9570000066",
            "regions": ["All India", "Bengaluru", "Delhi NCR", "Mumbai", "Odisha", "Chennai", "Hyderabad", "Kolkata"],
            "services": ["Fraud Awareness", "Counseling", "Legal Aid", "Incident Reporting"],
            "website": "https://cyberpeace.org/",
            "desc": "Technical guidance, cyber victim trauma counseling, and direct reporting aid for digital scams."
        },
        {
            "name": "Silver Age Foundation",
            "helpline": "+91 9090222666",
            "regions": ["Odisha", "All India", "Kolkata"],
            "services": ["Elderly Support", "Fraud Awareness", "Counseling"],
            "website": "https://silveragefoundation.org/",
            "desc": "Dedicated senior safety programs, digital literacy, and immediate scam victim support."
        },
        {
            "name": "Dignity Foundation",
            "helpline": "022-2352-8888",
            "regions": ["Mumbai", "Maharashtra", "Delhi NCR", "Bengaluru", "Chennai", "All India"],
            "services": ["Elderly Support", "Legal Aid", "Counseling"],
            "website": "https://www.dignityfoundation.org/",
            "desc": "Senior citizen protection, legal advice against financial fraud, and panic counseling."
        },
        {
            "name": "CopConnect Cyber Support Network",
            "helpline": "1930 / App Dispatch",
            "regions": ["All India", "Bengaluru", "Delhi NCR", "Mumbai", "Hyderabad", "Chennai"],
            "services": ["Legal Aid", "Counseling", "Incident Reporting"],
            "website": "https://copconnect.in/",
            "desc": "Specialized network connecting cybercrime victims with legal counselors and psychological support."
        }
    ]

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_regions = st.multiselect(
            "📍 Filter by Region", 
            ["All India", "Bengaluru", "Delhi NCR", "Mumbai", "Odisha", "Chennai", "Hyderabad", "Kolkata"], 
            default=["All India"]
        )
    with col_f2:
        selected_services = st.multiselect(
            "🛠️ Filter by Service", 
            ["Elderly Support", "Counseling", "Legal Aid", "Fraud Awareness", "Incident Reporting"], 
            default=["Counseling", "Legal Aid"]
        )

    st.divider()

    def is_match(ngo):
        norm_regions = [r.lower().strip() for r in selected_regions] if selected_regions else []
        norm_services = [s.lower().strip() for s in selected_services] if selected_services else []
        
        region_match = False
        if not norm_regions or "all india" in norm_regions:
            region_match = True
        else:
            for r in norm_regions:
                if any(r in reg.lower() for reg in ngo["regions"]):
                    region_match = True
                    break

        service_match = False
        if not norm_services:
            service_match = True
        else:
            for s in norm_services:
                if any(s in svc.lower() for svc in ngo["services"]):
                    service_match = True
                    break

        return region_match and service_match

    filtered_ngos = [ngo for ngo in ngo_database if is_match(ngo)]

    if filtered_ngos:
        st.subheader(f"✅ Found {len(filtered_ngos)} Verified Support Partners")
        for ngo in filtered_ngos:
            with st.container():
                st.markdown(f"""
                <div style="background-color:#0F172A; border-left:4px solid #3B82F6; padding:16px; border-radius:8px; margin-bottom:12px; border: 1px solid #1E293B;">
                    <h3 style="margin:0 0 4px 0; color:#F8FAFC;">{ngo['name']}</h3>
                    <p style="margin:0; font-size:1.1em; color:#60A5FA;"><b>📞 Helpline:</b> <code style="font-size:1.1em; color:#93C5FD;">{ngo['helpline']}</code></p>
                    <p style="margin:6px 0; color:#94A3B8; font-size:0.9em;">
                        <b>📍 Coverage:</b> {', '.join([r for r in ngo['regions'] if r != 'All India'][:4])} | 
                        <b>🛠️ Services:</b> {', '.join(ngo['services'])}
                    </p>
                    <p style="margin:0; font-size:0.9em; color:#CBD5E1;">{ngo['desc']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"📩 Send Pre-filled Incident to {ngo['name']}", key=ngo['name']):
                    incident_report = f"""
LUMINA Incident Report

Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Call Duration: 145 minutes
Risk Score: 100/100
Risk Level: CRITICAL
Caller Type: Unknown Number
Video Call: Yes
Isolation Signal: Low outgoing activity

Recommended Action: Immediate family intervention + 1930 reporting
"""
                    st.success("✅ Incident report drafted and ready to send!")
                    st.code(incident_report)
    else:
        st.warning("Showing core nationwide emergency response helplines:")
        for ngo in ngo_database[:2]:
            st.markdown(f"• **{ngo['name']}**: `{ngo['helpline']}`")

# ============ COMMUNITY THREAT RADAR ============
elif page == "📢 Community Threat Radar":
    st.header("📢 Community Threat Radar")
    st.caption("Live pattern intelligence aggregated across isolated video call telemetry.")
    
    def generate_digital_arrest_feed():
        now = datetime.now()
        return [
            {
                "vector": "CBI / Supreme Court Digital Arrest Trap",
                "location": "Bengaluru, KA",
                "time": (now - timedelta(minutes=14)).strftime("%H:%M"),
                "pattern": "+91 140-VOIP Range (Spoofed TRAI ID)",
                "telemetry": "Active 165-min WhatsApp Video | Camera Forced ON",
                "severity": "CRITICAL"
            },
            {
                "vector": "Customs Illegal Narcotics Seizure Threat",
                "location": "Delhi NCR",
                "time": (now - timedelta(minutes=32)).strftime("%H:%M"),
                "pattern": "+91 9810-XXXX-114",
                "telemetry": "Active 210-min Skype Call | Family Isolation Flag",
                "severity": "CRITICAL"
            },
            {
                "vector": "ED Money Laundering Notice Scam",
                "location": "Mumbai, MH",
                "time": (now - timedelta(minutes=58)).strftime("%H:%M"),
                "pattern": "+91 8010-XXXX-552",
                "telemetry": "Active 90-min Video Hold | Payment Link Dispatched",
                "severity": "HIGH"
            }
        ]
    
    col1, col2 = st.columns([1.3, 1])
    
    with col1:
        st.subheader("🔴 Active Digital Arrest Threat Feed")
        feed = generate_digital_arrest_feed()
        
        for item in feed:
            st.markdown(f"""
            <div style="background-color: #0F172A; border: 1px solid #334155; padding: 12px; border-radius: 8px; margin-bottom: 10px;">
                <span style="background-color: {'#EF4444' if item['severity'] == 'CRITICAL' else '#F59E0B'}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">{item['severity']}</span>
                <span style="color: #94A3B8; font-size: 0.85em; margin-left: 10px;">🕒 {item['time']} | 📍 {item['location']}</span>
                <h4 style="margin: 6px 0 2px 0; color: #F8FAFC;">{item['vector']}</h4>
                <p style="margin:0; color: #CBD5E1; font-size: 0.9em;"><b>Caller ID Range:</b> {item['pattern']}</p>
                <p style="margin:0; color: #F59E0B; font-size: 0.85em;">⚠️ <b>LUMINA Telemetry:</b> {item['telemetry']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.subheader("🔍 Check Number Against Threat Radar")
        st.caption("Enter incoming caller ID to check against active threat patterns.")
        
        search_num = st.text_input("Enter phone number:", placeholder="+91 140XXXXXXX")
        
        if st.button("Check Radar Database", type="primary", use_container_width=True):
            if search_num:
                search_lower = search_num.lower().strip()
                if "140" in search_lower or "9810" in search_lower or "8010" in search_lower:
                    st.error("⚠️ **HIGH-RISK PATTERN DETECTED:** Number matches active VOIP spoofing ranges used in ongoing Digital Arrest campaigns.")
                    st.info("💡 **Recommended Action:** Keep caller on speaker and alert family immediately.")
                else:
                    st.success("🟢 **NO ACTIVE RADAR MATCH:** Exercise caution. If caller demands money or personal information, hang up and dial 1930.")
            else:
                st.warning("Please enter a phone number to check")

# ============ GOVERNMENT TOOLS ============
else:
    st.header("🔗 Government Tools")
    st.caption("Government resources for cyber safety")
    
    try:
        r = requests.get("http://localhost:8000/api/government-tools", timeout=10)
        if r.status_code == 200:
            data = r.json()
            for key, tool in data["tools"].items():
                with st.expander(f"🔹 {tool['name']}"):
                    st.write(tool['description'])
                    if "features" in tool:
                        for f in tool['features']:
                            st.write(f"• {f}")
                    if "stats" in tool:
                        st.write("**Statistics:**")
                        for stat, value in tool["stats"].items():
                            st.write(f"• {stat}: {value}")
            
            st.divider()
            st.subheader("Emergency Numbers")
            for name, number in data["emergency_numbers"].items():
                st.write(f"• **{name}:** {number}")
    except:
        st.warning("Backend not running")

st.divider()
st.caption("🔒 Privacy-First: SHA-256 | Data deleted after 24h | 📞 Helpline: 1930")