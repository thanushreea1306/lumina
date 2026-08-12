# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import AliasChoices, BaseModel, Field
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
from app.core.risk_engine import RiskEngine
from app.core.db import get_incidents

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

# ML artifact loading and status are owned by RiskEngine; see current_model_status().
# ============ PYDANTIC MODELS ============
class CallFeatures(BaseModel):
    call_duration_min: float
    is_unknown_number: int
    is_video_call: int
    hour_of_day: int
    caller_call_history: int
    outgoing_activity_ratio: float
    day_of_week: int
    extra_telemetry: Optional[dict] = None

class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    top_factors: List[str]
    features: dict
    alert_message: str
    model_used: str
    explanation: str = ""
    model_status: str = "unavailable"
    error_detail: Optional[str] = None
    ml_probability: Optional[float] = None
    rule_contribution: Optional[float] = None
    ml_cap_applied: Optional[str] = None
    safety_rule_contributions: List[dict] = Field(default_factory=list)
    missing_telemetry: List[str] = Field(default_factory=list)


class IsolationTelemetryRequest(BaseModel):
    """Validated body for POST /api/detect-isolation.

    All fields are optional. An explicit null is treated as missing telemetry
    by the engine (identical to an absent field); an explicit 0 / False stays
    a real observation. Invalid types are rejected by Pydantic at the API
    boundary with a normal 422 response.
    """

    call_duration_minutes: Optional[float] = Field(
        default=None, alias=AliasChoices("call_duration_minutes", "call_duration_min")
    )
    is_unknown_number: Optional[bool] = None
    is_video_call: Optional[bool] = None
    hour_of_day: Optional[int] = None
    caller_call_history: Optional[int] = None
    outgoing_activity_ratio: Optional[float] = None
    day_of_week: Optional[int] = None
    is_weekend: Optional[bool] = None
    screen_time_on_call_percent: Optional[float] = None
    num_app_switches: Optional[int] = None
    num_home_presses: Optional[int] = None
    has_sms_activity: Optional[bool] = None
    has_social_app_activity: Optional[bool] = None
    location_change: Optional[float] = None
    screen_brightness: Optional[float] = None
    screen_on_continuous_hours: Optional[float] = None
    persistence_hours: Optional[float] = None

# ============ INITIALIZE SERVICES ============
ngo_support = NGOSupport()
community_alerts = CommunityAlerts()
risk_engine = RiskEngine()


def current_model_status() -> dict:
    """Single authoritative ML status, delegated to the shared RiskEngine."""
    if not risk_engine.loaded:
        risk_engine.load()
    return {
        "model_status": risk_engine.model_status,
        "error_detail": risk_engine.error_detail,
        "features": risk_engine.model_features,
    }

# ============ ROUTERS ============
app.include_router(detect.router, prefix="/api/detect", tags=["Detection"])

def _coerce_call_payload(features) -> dict:
    payload = features.model_dump() if hasattr(features, "dict") else dict(features)
    extra = payload.pop("extra_telemetry", None) or {}
    payload.update(extra)
    payload["call_duration_min"] = payload.get("call_duration_min", payload.get("call_duration_minutes", 0))
    payload["is_unknown_number"] = payload.get("is_unknown_number", 0)
    payload["is_video_call"] = payload.get("is_video_call", 0)
    payload["hour_of_day"] = payload.get("hour_of_day", 12)
    payload["caller_call_history"] = payload.get("caller_call_history", 0)
    payload["outgoing_activity_ratio"] = payload.get("outgoing_activity_ratio", 0.5)
    return payload


def _coerce_isolation_payload(telemetry: dict) -> dict:
    payload = dict(telemetry or {})
    payload["call_duration_min"] = payload.get("call_duration_minutes", payload.get("call_duration_min", 0))
    payload["is_unknown_number"] = int(bool(payload.get("is_unknown_number", False)))
    payload["is_video_call"] = int(bool(payload.get("is_video_call", False)))
    payload["hour_of_day"] = payload.get("hour_of_day", 12)
    payload["caller_call_history"] = payload.get("caller_call_history", 0)
    payload["outgoing_activity_ratio"] = payload.get("outgoing_activity_ratio", 0.5)
    if "screen_time_on_call_percent" in payload:
        payload["screen_time_on_call_percent"] = payload.get("screen_time_on_call_percent", 0)
    if "num_app_switches" in payload:
        payload["num_app_switches"] = payload.get("num_app_switches", 0)
    if "num_home_presses" in payload:
        payload["num_home_presses"] = payload.get("num_home_presses", 0)
    if "has_sms_activity" in payload and payload["has_sms_activity"] is not None:
        payload["has_sms_activity"] = int(bool(payload["has_sms_activity"]))
    if "has_social_app_activity" in payload and payload["has_social_app_activity"] is not None:
        payload["has_social_app_activity"] = int(bool(payload["has_social_app_activity"]))
    if "location_change" in payload:
        payload["location_change"] = payload.get("location_change", 0)
    if "screen_brightness" in payload:
        payload["screen_brightness"] = payload.get("screen_brightness", 0)
    if "screen_on_continuous_hours" in payload:
        payload["screen_on_continuous_hours"] = payload.get("screen_on_continuous_hours", 0)
    if "persistence_hours" in payload:
        payload["persistence_hours"] = payload.get("persistence_hours", 0)
    return payload


def _explainable_factors(risk_result: dict) -> list[str]:
    reasons = []
    for item in risk_result.get("safety_rule_contributions", []):
        if item.get("active"):
            reasons.append(item.get("reason", "Safety signal"))
    if not reasons:
        explanation = risk_result.get("explanation", "")
        summary = (
            explanation.get("summary")
            if isinstance(explanation, dict)
            else (explanation or "No major risk indicators")
        )
        reasons.append(summary)
    return reasons[:3]


# ============ ROOT AND HEALTH ENDPOINTS ============
@app.get("/")
async def root():
    status = current_model_status()
    return {
        "project": "LUMINA",
        "tagline": "Illuminating the Digital Arrest Trap",
        "version": "2.0.0",
        "status": "operational",
        "model_loaded": status["model_status"] == "available",
        "model_status": status["model_status"],
        "error_detail": status["error_detail"],
        "docs": "/docs",
        "model_info": {
            "type": "XGBoost Call Features Model",
            "features": status["features"]
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
    status = current_model_status()
    return {
        "status": "healthy",
        "model_loaded": status["model_status"] == "available",
        "model_status": status["model_status"],
        "error_detail": status["error_detail"],
    }

# ============ CORE SCORING ENDPOINT ============
@app.post("/api/score", response_model=RiskResponse)
async def score_call(features: CallFeatures):
    try:
        payload = _coerce_call_payload(features)
        risk_result = risk_engine.score(payload)
        risk_level = risk_result["risk_level"].lower()
        factors = _explainable_factors(risk_result)

        if risk_level == "critical":
            alert = f"""🚨 LUMINA CRITICAL ALERT!

Digital arrest scam pattern detected!
- Duration: {payload.get('call_duration_min', 0):.0f} minutes
- Unknown caller: {"Yes" if payload.get('is_unknown_number', 0) else "No"}
- Video call: {"Yes" if payload.get('is_video_call', 0) else "No"}

Actions: Call them on another line. Visit if possible. Dial 1930 if confirmed."""
        elif risk_level == "high":
            alert = "LUMINA: High risk call detected. Monitor closely."
        elif risk_level == "medium":
            alert = "LUMINA: Moderate risk indicators detected."
        else:
            alert = "LUMINA: No significant risk detected."

        return RiskResponse(
            risk_score=risk_result["risk_score"],
            risk_level=risk_level,
            top_factors=factors if factors else ["No significant risk"],
            features=payload,
            alert_message=alert,
            model_used=risk_result.get("model_status", "unavailable"),
            explanation=risk_result.get("explanation", ""),
            model_status=risk_result.get("model_status", "unavailable"),
            error_detail=risk_result.get("error_detail"),
            ml_probability=risk_result.get("ml_probability"),
            rule_contribution=risk_result.get("rule_contribution"),
            ml_cap_applied=risk_result.get("ml_cap_applied"),
            safety_rule_contributions=risk_result.get("safety_rule_contributions", []),
            missing_telemetry=risk_result.get("missing_telemetry", []),
        )
    except Exception as e:
        print(f"Error in /api/score: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ HISTORY / INCIDENTS ============
@app.get("/api/incidents")
async def incidents(limit: int = 50):
    """Return recent incident history from SQLite."""
    try:
        records = get_incidents(limit)
    except Exception as e:
        print(f"Error in /api/incidents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "total": len(records),
        "incidents": records
    }

# ============ OTHER ENDPOINTS ============
@app.post("/api/generate-report")
async def create_report(features: CallFeatures):
    payload = _coerce_call_payload(features)
    risk_result = risk_engine.score(payload)
    risk_level = risk_result["risk_level"].lower()
    risk_data = {
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_level,
        "top_factors": _explainable_factors(risk_result)
    }

    pdf_path = generate_fir_report(payload, risk_data)

    return {
        "status": "success",
        "pdf_path": pdf_path,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_level,
        "message": f"PDF report generated: {pdf_path}"
    }

@app.get("/api/download-report/{filename}")
async def download_report(filename: str):
    reports_dir = os.path.abspath("reports")
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=404, detail="Report not found")
    file_path = os.path.abspath(os.path.join(reports_dir, safe_name))
    if not file_path.startswith(reports_dir + os.sep):
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(file_path, media_type="application/pdf", filename=safe_name)

@app.post("/api/send-alert")
async def send_alert(features: CallFeatures, elder_name: str = "Family Member"):
    payload = _coerce_call_payload(features)
    risk_result = risk_engine.score(payload)
    risk_level = risk_result["risk_level"].lower()

    alert_result = send_family_alert(
        elder_name=elder_name,
        risk_level=risk_level,
        duration=payload.get("call_duration_min", 0),
        features=payload
    )

    delivery_status = alert_result.get("delivery_status")
    delivered = delivery_status == "SENT"

    return {
        "status": "success",
        "alert_sent": delivered,
        "delivered": delivered,
        "delivery_status": delivery_status,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_level,
        "message": alert_result.get("alert"),
        "reason": alert_result.get("reason"),
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
    }

# ============ SILENT INTERVENTION ENDPOINT ============
@app.post("/api/silent-intervention")
async def silent_intervention(features: CallFeatures, victim_name: str = "Family Member"):
    """Trigger silent intervention without victim action"""
    payload = _coerce_call_payload(features)
    risk_result = risk_engine.score(payload)
    score = risk_result["risk_score"]

    factors = _explainable_factors(risk_result)

    panic_trigger = PanicTrigger()
    intervention = panic_trigger.trigger_silent_intervention(
        victim_name=victim_name,
        risk_score=score,
        risk_factors=factors if factors else ["No significant risk"],
        risk_level=risk_result["risk_level"],
    )

    return intervention

# ============ ISOLATION DETECTION ENDPOINT (NEW) ============
@app.post("/api/detect-isolation")
async def detect_isolation(telemetry: IsolationTelemetryRequest):
    """Receive device telemetry and return isolation risk score.

    The request body is validated by IsolationTelemetryRequest: malformed
    payloads and wrong types are rejected with 422 before reaching the
    engine. Explicit null means missing telemetry; explicit 0 / False are
    real observations.
    """
    try:
        payload = _coerce_isolation_payload(telemetry.model_dump())
        risk_result = risk_engine.score(payload)
        risk_level = risk_result["risk_level"].upper()
        factors = [item.get("reason", "Signal") for item in risk_result.get("safety_rule_contributions", []) if item.get("active")][:5]

        result = {
            "isolation_score": risk_result["risk_score"],
            "risk_level": risk_level,
            "risk_factors": factors,
            "total_factors": len(factors),
            "alert_triggered": risk_result["risk_level"] in {"high", "critical"},
            "explanation": risk_result.get("explanation", {}),
            "model_status": risk_result.get("model_status", "unavailable"),
            "error_detail": risk_result.get("error_detail"),
        }

        if result["alert_triggered"]:
            result["alert_message"] = (
                f"🚨 LUMINA SAFETY ALERT - {risk_level}\n"
                f"Risk Score: {risk_result['risk_score']:.1f}%"
            )

        return result
    except Exception as e:
        print(f"Error in /api/detect-isolation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))