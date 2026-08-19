"""
Services layer package for Zentrix.ai.
Reference: ARCHITECTURE.md §4 (app/services)
"""

from app.services.connection_service import ConnectionService, connection_service

__all__ = [
    "ConnectionService",
    "connection_service",
]
