"""Main FastAPI Application Entry Point for Zentrix.ai.

Reference: ARCHITECTURE.md §4 (app/main.py), §10 & PRD.md §12
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ZentrixException, format_error_response
from app.core.logging import get_logger, setup_logging
from app.db.session import check_db_health, dispose_db_engine

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifespan context manager."""
    # ── Startup ──
    setup_logging(environment=settings.ENVIRONMENT)
    logger.info(
        f"Starting Zentrix.ai API in {settings.ENVIRONMENT} mode",
        extra={"environment": settings.ENVIRONMENT, "api_prefix": settings.API_V1_PREFIX},
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
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers (Step 32) ──────────────────────────────────────

@app.exception_handler(ZentrixException)
async def zentrix_exception_handler(request: Request, exc: ZentrixException) -> JSONResponse:
    """Handles domain-specific Zentrix exceptions with standardized envelopes."""
    logger.warning(
        f"ZentrixException [{exc.code}]: {exc.message}",
        extra={"code": exc.code, "status_code": exc.status_code, "details": exc.details},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles FastAPI Pydantic request validation errors (422)."""
    errors = exc.errors()
    logger.info(f"Validation error on {request.method} {request.url.path}: {len(errors)} errors")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation_errors": errors},
        ),
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """Handles RBAC permission errors (403)."""
    logger.warning(f"Permission denied on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=format_error_response(
            code="FORBIDDEN",
            message=str(exc),
            status_code=status.HTTP_403_FORBIDDEN,
        ),
    )


@app.exception_handler(LookupError)
async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
    """Handles resource lookup errors (404)."""
    logger.info(f"Resource not found on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=format_error_response(
            code="NOT_FOUND",
            message=str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handles client argument/value validation errors (400)."""
    logger.warning(f"Value error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=format_error_response(
            code="BAD_REQUEST",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handles standard HTTP exceptions."""
    code_map = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code=code_map.get(exc.status_code, "HTTP_ERROR"),
            message=str(exc.detail),
            status_code=exc.status_code,
        ),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled internal exceptions (500)."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal error occurred. Our engineers have been alerted.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    )


# ── Health Check Endpoints ───────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root() -> dict[str, Any]:
    """Root endpoint returning service identity and status."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Service health check verifying application database reachability."""
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
