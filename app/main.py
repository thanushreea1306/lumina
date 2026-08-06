# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime

from app.services.report_generator import generate_fir_report
from app.services.alert import send_family_alert
from app.services.panic_trigger import PanicTrigger
from app.services.senior_protection import SeniorProtection
from app.services.government_integration import GovernmentIntegration
from app.services.ngo_support import NGOSupport
from app.services.community_alerts import CommunityAlerts
from app.api import detect

app = FastAPI(
    title="LUMINA",
    description="Illuminating the Digital Arrest Trap",
    version="2.0.0"
)

# CORS - Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ MODEL LOADING ============
MODEL_PATH = "models/saved/risk_classifier.pkl"
SCALER_PATH = "models/saved/scaler.pkl"
model = None
scaler = None
FEATURES = None

def load_models():
    global model, scaler, FEATURES
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        try:
            FEATURES = joblib.load('models/saved/features.pkl')
        except:
            FEATURES = ['call_duration_min', 'is_unknown_number', 'is_video_call', 
                       'hour_of_day', 'caller_call_history', 'outgoing_activity_ratio',
                       'is_weekend', 'call_duration_log', 'is_early_morning', 
                       'is_late_night', 'activity_category']
        return True
    return False

# ============ PYDANTIC MODELS ============
class CallFeatures(BaseModel):
    call_duration_min: float
    is_unknown_number: int
    is_video_call: int
    hour_of_day: int
    caller_call_history: int
    outgoing_activity_ratio: float
    day_of_week: int

class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    top_factors: List[str]
    features: dict
    alert_message: str
    model_used: str

# ============ INITIALIZE SERVICES ============
ngo_support = NGOSupport()
community_alerts = CommunityAlerts()

# ============ ROUTERS ============
app.include_router(detect.router, prefix="/api/detect", tags=["Detection"])

# ============ ROOT AND HEALTH ENDPOINTS ============
@app.get("/")
async def root():
    return {
        "project": "LUMINA",
        "tagline": "Illuminating the Digital Arrest Trap",
        "version": "2.0.0",
        "status": "operational",
        "model_loaded": load_models(),
        "docs": "/docs",
        "model_info": {
            "type": "XGBoost Call Features Model",
            "features": FEATURES
        },
        "features": {
            "panic_detection": True,
            "senior_protection": True,
            "government_integration": True,
            "ngo_support": True,
            "community_alerts": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": load_models()}

# ============ CORE SCORING ENDPOINT ============
@app.post("/api/score", response_model=RiskResponse)
async def score_call(features: CallFeatures):
    try:
        if not load_models():
            raise HTTPException(status_code=503, detail="Model not trained yet")
        
        # Extract features
        call_duration_min = features.call_duration_min
        is_unknown_number = features.is_unknown_number
        is_video_call = features.is_video_call
        hour_of_day = features.hour_of_day
        caller_call_history = features.caller_call_history
        outgoing_activity_ratio = features.outgoing_activity_ratio
        
        # Derived features
        is_weekend = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
        call_duration_log = np.log1p(call_duration_min)
        is_early_morning = 1 if 5 <= hour_of_day <= 8 else 0
        is_late_night = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
        
        if outgoing_activity_ratio < 0.33:
            activity_category = 0
        elif outgoing_activity_ratio < 0.66:
            activity_category = 1
        else:
            activity_category = 2
        
        # Create DataFrame with all 11 features
        X = pd.DataFrame([{
            'call_duration_min': call_duration_min,
            'is_unknown_number': is_unknown_number,
            'is_video_call': is_video_call,
            'hour_of_day': hour_of_day,
            'caller_call_history': caller_call_history,
            'outgoing_activity_ratio': outgoing_activity_ratio,
            'is_weekend': is_weekend,
            'call_duration_log': call_duration_log,
            'is_early_morning': is_early_morning,
            'is_late_night': is_late_night,
            'activity_category': activity_category
        }])
        
        # Scale and predict
        X_scaled = scaler.transform(X)
        proba = model.predict_proba(X_scaled)[0][1]
        score = round(proba * 100, 1)
        
        # Risk factors
        factors = []
        if call_duration_min > 60:
            factors.append("Long call duration")
        if is_unknown_number == 1:
            factors.append("Unknown caller")
        if is_video_call == 1:
            factors.append("Video call")
        if outgoing_activity_ratio < 0.3:
            factors.append("Low outgoing activity")
        if caller_call_history < 2:
            factors.append("First-time caller")
        
        # Risk level
        if score >= 70:
            risk_level = "critical"
            alert = f"""🚨 LUMINA CRITICAL ALERT!

Digital arrest scam pattern detected!
- Duration: {call_duration_min:.0f} minutes
- Unknown caller: {"Yes" if is_unknown_number else "No"}
- Video call: {"Yes" if is_video_call else "No"}

Actions: Call them on another line. Visit if possible. Dial 1930 if confirmed."""
        elif score >= 40:
            risk_level = "high"
            alert = "⚠️ LUMINA: High risk call detected. Monitor closely."
        elif score >= 20:
            risk_level = "medium"
            alert = "⚠️ LUMINA: Moderate risk indicators detected."
        else:
            risk_level = "low"
            alert = "✅ LUMINA: No significant risk detected."
        
        return RiskResponse(
            risk_score=score,
            risk_level=risk_level,
            top_factors=factors[:3] if factors else ["No significant risk"],
            features=features.dict(),
            alert_message=alert,
            model_used="XGBoost (Call Features Model)"
        )
    except Exception as e:
        print(f"Error in /api/score: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ OTHER ENDPOINTS ============
@app.post("/api/generate-report")
async def create_report(features: CallFeatures):
    if not load_models():
        raise HTTPException(status_code=503, detail="Model not trained yet")
    
    call_duration_min = features.call_duration_min
    is_unknown_number = features.is_unknown_number
    is_video_call = features.is_video_call
    hour_of_day = features.hour_of_day
    caller_call_history = features.caller_call_history
    outgoing_activity_ratio = features.outgoing_activity_ratio
    
    is_weekend = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
    call_duration_log = np.log1p(call_duration_min)
    is_early_morning = 1 if 5 <= hour_of_day <= 8 else 0
    is_late_night = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
    
    if outgoing_activity_ratio < 0.33:
        activity_category = 0
    elif outgoing_activity_ratio < 0.66:
        activity_category = 1
    else:
        activity_category = 2
    
    X = pd.DataFrame([{
        'call_duration_min': call_duration_min,
        'is_unknown_number': is_unknown_number,
        'is_video_call': is_video_call,
        'hour_of_day': hour_of_day,
        'caller_call_history': caller_call_history,
        'outgoing_activity_ratio': outgoing_activity_ratio,
        'is_weekend': is_weekend,
        'call_duration_log': call_duration_log,
        'is_early_morning': is_early_morning,
        'is_late_night': is_late_night,
        'activity_category': activity_category
    }])
    
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[0][1]
    score = round(proba * 100, 1)
    
    factors = []
    if call_duration_min > 60:
        factors.append("Long call duration")
    if is_unknown_number == 1:
        factors.append("Unknown caller")
    if is_video_call == 1:
        factors.append("Video call")
    if outgoing_activity_ratio < 0.3:
        factors.append("Low outgoing activity")
    if caller_call_history < 2:
        factors.append("First-time caller")
    
    if score >= 70:
        risk_level = "critical"
    elif score >= 40:
        risk_level = "high"
    elif score >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    risk_data = {
        "risk_score": score,
        "risk_level": risk_level,
        "top_factors": factors[:3] if factors else ["No significant risk"]
    }
    
    pdf_path = generate_fir_report(features.dict(), risk_data)
    
    return {
        "status": "success",
        "pdf_path": pdf_path,
        "risk_score": score,
        "risk_level": risk_level,
        "message": f"PDF report generated: {pdf_path}"
    }

@app.get("/api/download-report/{filename}")
async def download_report(filename: str):
    file_path = f"reports/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)

@app.post("/api/send-alert")
async def send_alert(features: CallFeatures, elder_name: str = "Family Member"):
    if not load_models():
        raise HTTPException(status_code=503, detail="Model not trained yet")
    
    call_duration_min = features.call_duration_min
    is_unknown_number = features.is_unknown_number
    is_video_call = features.is_video_call
    hour_of_day = features.hour_of_day
    caller_call_history = features.caller_call_history
    outgoing_activity_ratio = features.outgoing_activity_ratio
    
    is_weekend = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
    call_duration_log = np.log1p(call_duration_min)
    is_early_morning = 1 if 5 <= hour_of_day <= 8 else 0
    is_late_night = 1 if hour_of_day >= 22 or hour_of_day <= 4 else 0
    
    if outgoing_activity_ratio < 0.33:
        activity_category = 0
    elif outgoing_activity_ratio < 0.66:
        activity_category = 1
    else:
        activity_category = 2
    
    X = pd.DataFrame([{
        'call_duration_min': call_duration_min,
        'is_unknown_number': is_unknown_number,
        'is_video_call': is_video_call,
        'hour_of_day': hour_of_day,
        'caller_call_history': caller_call_history,
        'outgoing_activity_ratio': outgoing_activity_ratio,
        'is_weekend': is_weekend,
        'call_duration_log': call_duration_log,
        'is_early_morning': is_early_morning,
        'is_late_night': is_late_night,
        'activity_category': activity_category
    }])
    
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[0][1]
    score = round(proba * 100, 1)
    
    if score >= 70:
        risk_level = "critical"
    elif score >= 40:
        risk_level = "high"
    else:
        risk_level = "low"
    
    alert_message = send_family_alert(
        elder_name=elder_name,
        risk_level=risk_level,
        duration=call_duration_min,
        features=features.dict()
    )
    
    return {
        "status": "success",
        "alert_sent": True,
        "risk_score": score,
        "risk_level": risk_level,
        "message": alert_message,
        "timestamp": datetime.now().isoformat()
    }

# ============ SENIOR PROTECTION ============
@app.get("/api/ngos")
async def get_ngos():
    senior = SeniorProtection()
    return {
        "ngos": senior.get_ngo_list(),
        "total": len(senior.get_ngo_list())
    }

@app.get("/api/senior-guide")
async def get_senior_guide():
    senior = SeniorProtection()
    return senior.get_senior_support_guide()

@app.get("/api/awareness-material")
async def get_awareness_material():
    senior = SeniorProtection()
    return {
        "material": senior.generate_awareness_material(),
        "format": "text"
    }

# ============ GOVERNMENT TOOLS ============
@app.get("/api/government-tools")
async def get_government_tools():
    gov = GovernmentIntegration()
    return {
        "tools": gov.get_all_tools(),
        "emergency_numbers": gov.get_emergency_numbers()
    }

@app.get("/api/integration-guide")
async def get_integration_guide():
    gov = GovernmentIntegration()
    return {
        "guide": gov.generate_integration_guide()
    }

# ============ NGO SUPPORT ============
@app.get("/api/ngos/all")
async def get_all_ngos():
    return {
        "ngos": ngo_support.get_all_ngos(),
        "total": len(ngo_support.get_all_ngos())
    }

@app.get("/api/ngos/region/{region}")
async def get_ngos_by_region(region: str):
    return {
        "region": region,
        "ngos": ngo_support.get_ngos_by_region(region),
        "count": len(ngo_support.get_ngos_by_region(region))
    }

@app.get("/api/ngos/service/{service}")
async def get_ngos_by_service(service: str):
    return {
        "service": service,
        "ngos": ngo_support.get_ngos_by_service(service),
        "count": len(ngo_support.get_ngos_by_service(service))
    }

@app.get("/api/awareness-kit")
async def get_awareness_kit():
    return ngo_support.get_awareness_kit()

@app.get("/api/elderly-guide")
async def get_elderly_guide():
    return ngo_support.get_elderly_guide()

@app.post("/api/ngo-request")
async def submit_ngo_request(ngo_id: str, request_type: str, details: dict):
    return ngo_support.submit_ngo_request(ngo_id, request_type, details)

# ============ COMMUNITY ALERTS ============
@app.get("/api/community-alerts")
async def get_community_alerts():
    return {
        "alerts": community_alerts.get_active_alerts(),
        "total": len(community_alerts.get_active_alerts())
    }

@app.post("/api/community-alert")
async def create_community_alert(scam_type: str, description: str, severity: str, location: str):
    alert = community_alerts.create_alert(scam_type, description, severity, location)
    return alert

@app.post("/api/subscribe-alerts")
async def subscribe_to_alerts(phone: str, location: str):
    return community_alerts.subscribe_to_alerts(phone, location)

@app.get("/api/alerts/location/{location}")
async def get_alerts_by_location(location: str):
    return {
        "location": location,
        "alerts": community_alerts.get_alerts_by_location(location),
        "count": len(community_alerts.get_alerts_by_location(location))

 # ============ SILENT INTERVENTION ENDPOINT ============
@app.post("/api/silent-intervention")
async def silent_intervention(features: CallFeatures, victim_name: str = "Family Member"):
    """Trigger silent intervention without victim action"""
    
    if not load_models():
        raise HTTPException(status_code=503, detail="Model not trained yet")
    
    # Score the call
    X = pd.DataFrame([{
        'call_duration_min': features.call_duration_min,
        'is_unknown_number': features.is_unknown_number,
        'is_video_call': features.is_video_call,
        'hour_of_day': features.hour_of_day,
        'caller_call_history': features.caller_call_history,
        'outgoing_activity_ratio': features.outgoing_activity_ratio
    }])
    
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[0][1]
    score = round(proba * 100, 1)
    
    # Risk factors
    factors = []
    if features.call_duration_min > 60:
        factors.append("Long call duration")
    if features.is_unknown_number == 1:
        factors.append("Unknown caller")
    if features.is_video_call == 1:
        factors.append("Video call")
    if features.outgoing_activity_ratio < 0.3:
        factors.append("Low outgoing activity")
    if features.caller_call_history < 2:
        factors.append("First-time caller")
    
    # Generate silent intervention
    panic_trigger = PanicTrigger()
    intervention = panic_trigger.trigger_silent_intervention(
        victim_name=victim_name,
        risk_score=score,
        risk_factors=factors[:3] if factors else ["No significant risk"]
    )
    
    return intervention
   }