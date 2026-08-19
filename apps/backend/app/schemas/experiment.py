"""
Optimization Experiment, Verification, Approval, and Canary Pydantic Schemas.
Reference: PRD.md §5 Feature 2, §13 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelPredictionBase(BaseModel):
    model_version: str
    prediction: float
    lower_bound: float
    upper_bound: float
    confidence: float
    actual: Optional[float] = None
    absolute_error: Optional[float] = None
    features_snapshot: Optional[Dict[str, Any]] = None


class ModelPredictionCreate(ModelPredictionBase):
    experiment_id: uuid.UUID


class ModelPredictionOut(ModelPredictionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    created_at: datetime


class BanditEventBase(BaseModel):
    context: Dict[str, Any]
    action: str
    propensity: float
    reward: Optional[float] = None
    success: bool = False
    model_version: str


class BanditEventCreate(BanditEventBase):
    connection_id: uuid.UUID
    experiment_id: Optional[uuid.UUID] = None


class BanditEventOut(BanditEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    experiment_id: Optional[uuid.UUID] = None
    created_at: datetime


class ApprovalBase(BaseModel):
    action: str = Field(..., description="Approval verdict ('APPROVE', 'REJECT')")
    reason: Optional[str] = Field(None, description="Human reviewer justification notes")


class ApprovalCreate(ApprovalBase):
    experiment_id: uuid.UUID


class ApprovalOut(ApprovalBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    user_id: uuid.UUID
    approved_at: datetime


class CanaryRunBase(BaseModel):
    status: str = Field(default="RUNNING", description="Canary state ('RUNNING', 'COMMITTED', 'ROLLED_BACK', 'FAILED')")
    canary_sql_applied: str
    observation_window_minutes: int = 15
    baseline_metrics: Optional[Dict[str, Any]] = None
    canary_metrics: Optional[Dict[str, Any]] = None
    rollback_reason: Optional[str] = None


class CanaryRunCreate(CanaryRunBase):
    experiment_id: uuid.UUID
    connection_id: uuid.UUID


class CanaryRunOut(CanaryRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    connection_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OptimizationExperimentBase(BaseModel):
    timestamp: datetime
    query_id: Optional[int] = None
    table_name: Optional[str] = None
    strategy: str = Field(..., description="Optimization strategy ('CREATE_INDEX', 'DROP_INDEX', 'ANALYZE', 'REWRITE', 'CONFIG')")
    candidate_sql: str
    baseline_latency: float = 0.0
    baseline_p95: float = 0.0
    baseline_cpu: float = 0.0
    baseline_io: float = 0.0
    candidate_latency: float = 0.0
    candidate_p95: float = 0.0
    candidate_cpu: float = 0.0
    candidate_io: float = 0.0
    predicted_latency_delta: float = 0.0
    actual_latency_delta: Optional[float] = None
    prediction_error: Optional[float] = None
    statistical_significance: bool = False
    confidence_interval_low: Optional[float] = None
    confidence_interval_high: Optional[float] = None
    skeptic_findings: Optional[Dict[str, Any]] = None
    policy_verdict: str = "PENDING"
    success: bool = False
    risk: str = "LOW"
    rollback: bool = False
    status: str = "PENDING"


class OptimizationExperimentCreate(OptimizationExperimentBase):
    connection_id: uuid.UUID
    diagnosis_id: Optional[uuid.UUID] = None


class OptimizationExperimentUpdate(BaseModel):
    actual_latency_delta: Optional[float] = None
    prediction_error: Optional[float] = None
    policy_verdict: Optional[str] = None
    success: Optional[bool] = None
    status: Optional[str] = None
    rollback: Optional[bool] = None


class OptimizationExperimentOut(OptimizationExperimentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    diagnosis_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ExperimentVerificationOut(BaseModel):
    experiment_id: uuid.UUID
    policy_verdict: str = Field(..., description="'VERIFIED', 'CONDITIONAL', or 'REJECTED'")
    statistical_significance: bool
    p_value: Optional[float] = None
    confidence_interval: List[float] = Field(default_factory=list)
    skeptic_critiques: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation_summary: str
    is_safe_for_canary: bool


class SimulationTriggerRequest(BaseModel):
    strategy: str
    candidate_sql: str
    table_name: Optional[str] = None
    query_id: Optional[int] = None
