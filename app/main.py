# app/main.py
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.evidence.router import router as evidence_router
from app.incident.router import router as incident_router

app = FastAPI(
    title="LUMINA",
    description="Digital Incident Protection — deterministic incident & safety engine",
    version="2.0.0",
)

logger = logging.getLogger(__name__)

# CORS — environment-driven production configuration.
# Development: localhost origins for the React dev server.
# Production: set LUMINA_CORS_ORIGINS env var (comma-separated).
def _get_cors_origins():
    env_origins = os.getenv("LUMINA_CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "https://lumina-1994.vercel.app",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ROUTERS ============
# The authoritative product surface is the HMAC-authenticated, owner-scoped
# incident + evidence routers. There is no unauthenticated inference/score
# endpoint: the deterministic safety engine is authoritative and ML is not
# part of production.
app.include_router(evidence_router, tags=["Evidence"])
app.include_router(incident_router, tags=["Incident"])


# ============ ROOT AND HEALTH ENDPOINTS ============
@app.get("/")
async def root():
    return {
        "project": "LUMINA",
        "tagline": "Digital Incident Protection",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "features": {
            "incident_engine": "deterministic (authoritative)",
            "recovery": "deterministic (completion never fabricated)",
            "trusted_contact": "configured delivery only",
            "transcription": "local faster-whisper",
        },
        "feature_status": {
            "senior_protection": "NOT_CONFIGURED - no live integration",
            "government_integration": "NOT_CONFIGURED - no live integration",
            "ngo_support": "NOT_CONFIGURED - no live integration",
            "community_alerts": "NOT_CONFIGURED - no live integration",
        },
        "integration_scope": "no external third-party integrations configured",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
