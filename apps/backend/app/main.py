"""
Main FastAPI Application Entry Point for Zentrix.ai.
Reference: ARCHITECTURE.md §4 (app/main.py), §10 & PRD.md §12
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import check_db_health, dispose_db_engine

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup and shutdown lifespan context manager.
    """
    # ── Startup ──
    setup_logging(environment=settings.ENVIRONMENT)
    logger.info(
        f"Starting Zentrix.ai API in {settings.ENVIRONMENT} mode",
        environment=settings.ENVIRONMENT,
        api_prefix=settings.API_V1_PREFIX,
    )

    # Verify database connection
    db_healthy = await check_db_health()
    if db_healthy:
        logger.info("Application database connection verified successfully")
    else:
        logger.warning("Application database connection check returned non-healthy status on startup")

    yield

    # ── Shutdown ──
    logger.info("Shutting down Zentrix.ai API, releasing connection pools...")
    from app.db.customer_db import customer_connection_manager
    await customer_connection_manager.close_all_pools()
    await dispose_db_engine()
    logger.info("Zentrix.ai API shutdown complete")



app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Autonomous Agentic Database Tuning & Performance Verification Engine",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ── Health Check Endpoints ───────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint returning service identity and status.
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Service health check verifying application database reachability.
    """
    db_healthy = await check_db_health()
    return JSONResponse(
        status_code=status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if db_healthy else "degraded",
            "database": "connected" if db_healthy else "disconnected",
            "environment": settings.ENVIRONMENT,
        },
    )


# ── Mount API Routers ────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
