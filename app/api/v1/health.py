"""app/api/v1/health.py — liveness and readiness check."""

from fastapi import APIRouter, Request
from app.schemas.responses import HealthResponse
from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check(request: Request) -> HealthResponse:
    """
    Returns API status, version, and number of records currently loaded in memory.
    Use this endpoint to verify the service is up and the ETL pipeline ran successfully.
    """
    df = request.app.state.df
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        records_loaded=len(df),
    )
