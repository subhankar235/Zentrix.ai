"""
Forecasting and Model Performance Pydantic Schemas.
Reference: PRD.md §5 Feature 3, §13 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DegradationCurvePoint(BaseModel):
    timestamp: datetime
    predicted_probability: float
    confidence_lower: float
    confidence_upper: float


class ForecastRecordBase(BaseModel):
    query_id: Optional[int] = None
    forecast_window_start: datetime
    forecast_window_end: datetime
    degradation_probability: float = Field(..., ge=0.0, le=1.0)
    probability_curve: Optional[List[Dict[str, Any]]] = None
    model_version: str
    is_flagged_for_action: bool = False


class ForecastRecordCreate(ForecastRecordBase):
    connection_id: uuid.UUID


class ForecastRecordOut(ForecastRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    created_at: datetime


class ForecastResponse(BaseModel):
    connection_id: uuid.UUID
    query_id: Optional[int] = None
    forecast_window_start: datetime
    forecast_window_end: datetime
    degradation_probability: float
    is_flagged_for_action: bool
    curve: List[DegradationCurvePoint] = Field(default_factory=list)
    suggested_strategies: List[str] = Field(default_factory=list)


class ModelDriftReportBase(BaseModel):
    model_name: str
    model_version: str
    dataset_drift_score: float = 0.0
    prediction_drift_score: float = 0.0
    metrics_payload: Optional[Dict[str, Any]] = None
    is_drift_detected: bool = False


class ModelDriftReportCreate(ModelDriftReportBase):
    pass


class ModelDriftReportOut(ModelDriftReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ModelPerformanceResponse(BaseModel):
    mae_over_time: List[Dict[str, Any]] = Field(default_factory=list)
    rmse_over_time: List[Dict[str, Any]] = Field(default_factory=list)
    calibration_score: float = 0.0
    drift_reports: List[ModelDriftReportOut] = Field(default_factory=list)
