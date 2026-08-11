# app/api/detect.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.panic_trigger import PanicTrigger

router = APIRouter()

class DetectRequest(BaseModel):
    text: str
    language: Optional[str] = "en"

class DetectResponse(BaseModel):
    is_scam: bool
    confidence: float
    risk_level: str
    risk_factors: List[str]
    method: str
    timestamp: str

@router.post("/panic", response_model=DetectResponse)
async def detect_panic(request: DetectRequest):
    """Detect scam using the rule-based phrase engine"""
    try:
        panic_trigger = PanicTrigger()
        result = panic_trigger.detect_panic(request.text)
        
        return DetectResponse(
            is_scam=result.get("panic_detected", False),
            confidence=float(result.get("risk_score", 0)),
            risk_level=result.get("severity", "low"),
            risk_factors=result.get("detected_phrases", []),
            method=result.get("method", "unknown"),
            timestamp=result.get("timestamp", "")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))