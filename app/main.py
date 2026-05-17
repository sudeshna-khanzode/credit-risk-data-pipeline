"""
etl-api-demo · main.py
=======================
FastAPI application entry point.
Mounts all routers and manages the data pipeline lifecycle.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import get_logger
from app.etl.pipeline import ETLPipeline
from app.api.v1 import health, summary, records, insights

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: run ETL once at startup, cache result in app.state
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting up — running ETL pipeline …")
    pipeline = ETLPipeline()
    app.state.df = pipeline.run()
    logger.info(f"✅ ETL complete — {len(app.state.df):,} clean records in memory.")
    yield
    logger.info("🛑 Shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Routers
    app.include_router(health.router,   prefix="/api/v1", tags=["Health"])
    app.include_router(summary.router,  prefix="/api/v1", tags=["ETL Summary"])
    app.include_router(records.router,  prefix="/api/v1", tags=["Records"])
    app.include_router(insights.router, prefix="/api/v1", tags=["Insights"])

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
