"""
Diagnosis and Evidence Graph Pydantic Schemas.
Reference: PRD.md §5 Feature 1, §13 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceGraphNodeBase(BaseModel):
    node_key: str
    node_type: str = Field(..., description="Node classification ('METRIC', 'ANOMALY', 'EVENT', 'HYPOTHESIS', 'ROOT_CAUSE')")
    label: str
    agent_domain: str = Field(..., description="Specialist agent domain ('PLANNER', 'CONCURRENCY', 'VACUUM', 'IO_BUFFER', 'SCHEMA_INDEX', 'SUPERVISOR')")
    confidence: float = 1.0
    metadata_payload: Optional[Dict[str, Any]] = None


class EvidenceGraphNodeCreate(EvidenceGraphNodeBase):
    diagnosis_id: uuid.UUID


class EvidenceGraphNodeOut(EvidenceGraphNodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    diagnosis_id: uuid.UUID
    created_at: datetime


class EvidenceGraphEdgeBase(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: str = Field(..., description="Relation type ('CAUSES', 'CORRELATES_WITH', 'CONTRIBUTES_TO', 'CONTRADICTS')")
    weight: float = 1.0
    explanation: Optional[str] = None


class EvidenceGraphEdgeCreate(EvidenceGraphEdgeBase):
    diagnosis_id: uuid.UUID


class EvidenceGraphEdgeOut(EvidenceGraphEdgeBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    diagnosis_id: uuid.UUID
    created_at: datetime


class EvidenceGraphOut(BaseModel):
    nodes: List[EvidenceGraphNodeOut] = Field(default_factory=list)
    edges: List[EvidenceGraphEdgeOut] = Field(default_factory=list)


class DiagnosisBase(BaseModel):
    title: str
    primary_root_cause: str = Field(
        ...,
        description="Ranked root cause (e.g. 'STALE_STATISTICS', 'PLAN_FLIP', 'LOCK_CONTENTION', 'VACUUM_LAG', 'INDEX_MISSING', 'BUFFER_PRESSURE')",
    )
    contributing_factors: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Secondary/contributing causal factors",
    )
    severity: str = Field(default="MEDIUM", description="Severity level ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model & agent confidence score")
    summary: str = Field(..., description="Deterministic and LLM causal summary narrative")
    validation_plan: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Counterfactual validation steps to confirm diagnosis",
    )
    status: str = Field(default="DETECTED", description="Status ('DETECTED', 'INVESTIGATING', 'CONFIRMED', 'RESOLVED', 'IGNORED')")


class DiagnosisCreate(DiagnosisBase):
    connection_id: uuid.UUID


class DiagnosisUpdate(BaseModel):
    title: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    validation_plan: Optional[Dict[str, Any]] = None


class DiagnosisOut(DiagnosisBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DiagnosisDetailOut(DiagnosisOut):
    evidence_graph: EvidenceGraphOut = Field(default_factory=EvidenceGraphOut)


class InvestigationTriggerRequest(BaseModel):
    connection_id: uuid.UUID
    time_window_minutes: int = Field(default=60, ge=5, le=1440)
    query_id: Optional[int] = None
