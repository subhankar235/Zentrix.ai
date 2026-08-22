"""Central API Router aggregation for Zentrix.ai Backend.

Reference: PRD.md §12 & ARCHITECTURE.md §4
"""

from fastapi import APIRouter
from app.api.routes import audit, auth, connections, diagnostics, experiments, forecasts, roi

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(connections.router)
api_router.include_router(diagnostics.router, prefix="/diagnostics")
api_router.include_router(diagnostics.router, prefix="/diagnoses")
api_router.include_router(experiments.router)
api_router.include_router(forecasts.router)
api_router.include_router(roi.router)
api_router.include_router(audit.router)
