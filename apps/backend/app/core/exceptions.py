"""Domain-Specific Exceptions & Standardized Error Schemas.

Covers all PRD failure cases:
- Insufficient telemetry (cold-start fallback)
- Shadow DB provisioning failures (labeled fallback, never silently upgraded)
- Underpowered statistical testing (downgraded to CONDITIONAL)
- Missing ROI pricing configuration (marked 'not configured')
- RBAC authorization & human approval gate blocks
- Policy engine validation violations

Reference: PRD.md §5, §12, §15, §22, §24 & ARCHITECTURE.md §4.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ZentrixException(Exception):
    """Base exception for all Zentrix domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(ZentrixException):
    """Authentication failure (invalid or expired JWT credentials)."""

    def __init__(self, message: str = "Invalid authentication credentials", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="UNAUTHENTICATED", status_code=401, details=details)


class AuthorizationError(ZentrixException):
    """Role-based authorization failure (e.g. non-DBA attempting approval)."""

    def __init__(self, message: str = "Unauthorized action for current user role", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="FORBIDDEN", status_code=403, details=details)


class ResourceNotFoundError(ZentrixException):
    """Requested database entity not found."""

    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404, details=details)


class InsufficientTelemetryError(ZentrixException):
    """Monitored database has insufficient telemetry (< 12 query/table snapshots)."""

    def __init__(self, message: str = "Insufficient historical telemetry for statistical confidence", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="INSUFFICIENT_TELEMETRY", status_code=422, details=details)


class ShadowDBProvisioningError(ZentrixException):
    """Shadow DB Docker container provisioning failed (falls back to labeled estimate)."""

    def __init__(self, message: str = "Shadow database simulation container could not be provisioned", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="SHADOW_DB_PROVISION_FAILED", status_code=503, details=details)


class UnderpoweredStatisticalTestError(ZentrixException):
    """Paired replay sample size insufficient (< 30) — downgraded to CONDITIONAL."""

    def __init__(self, message: str = "Experiment underpowered due to low sample count", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="STATISTICAL_TEST_UNDERPOWERED", status_code=422, details=details)


class UnconfiguredPricingTierError(ZentrixException):
    """ROI translation requested for an unconfigured cloud pricing tier."""

    def __init__(self, message: str = "Pricing tier cost model is not configured", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="COST_MODEL_NOT_CONFIGURED", status_code=422, details=details)


class PolicyViolationError(ZentrixException):
    """Candidate DDL or optimization violates hard safety policy checks."""

    def __init__(self, message: str = "Candidate optimization violated safety policy", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, code="POLICY_VIOLATION", status_code=422, details=details)


def format_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Standardized JSON error envelope per PRD.md §12."""
    return {
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        }
    }
