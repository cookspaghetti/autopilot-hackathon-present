# app/routers/health.py
"""
Health check endpoints.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def read_health():
    """
    Liveness probe.
    Public via public.map.json.
    """
    return {"status": "ok"}


@router.get("/ready")
def read_ready():
    """
    Readiness probe.
    Public via public.map.json.
    """
    return {"status": "ready"}
