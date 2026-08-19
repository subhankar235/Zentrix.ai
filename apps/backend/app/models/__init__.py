"""
SQLAlchemy models module re-exporting all database models.
Reference: PRD.md §13 & ARCHITECTURE.md §7
"""

from app.db.base import Base, TimestampMixin
from app.models.user import User
from app.models.connection import DatabaseConnection
from app.models.telemetry import QueryMetric, TableMetric, PlanMetric
from app.models.diagnosis import Diagnosis, EvidenceGraphNode, EvidenceGraphEdge
from app.models.experiment import OptimizationExperiment, ModelPrediction, BanditEvent
from app.models.forecast import ForecastRecord, ModelDriftReport
from app.models.roi import RoiRecord
from app.models.approval import Approval
from app.models.audit import AuditLog, CanaryRun

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "DatabaseConnection",
    "QueryMetric",
    "TableMetric",
    "PlanMetric",
    "Diagnosis",
    "EvidenceGraphNode",
    "EvidenceGraphEdge",
    "OptimizationExperiment",
    "ModelPrediction",
    "BanditEvent",
    "ForecastRecord",
    "ModelDriftReport",
    "RoiRecord",
    "Approval",
    "AuditLog",
    "CanaryRun",
]
