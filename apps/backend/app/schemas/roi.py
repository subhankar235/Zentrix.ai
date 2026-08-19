"""
ROI and Cost-to-Dollar Calculation Pydantic Schemas.
Reference: PRD.md §5 Feature 4, §13 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RoiRecordBase(BaseModel):
    estimated_monthly_savings_usd: float = Field(..., description="Projected monthly USD savings")
    compute_savings_usd: float = 0.0
    storage_savings_usd: float = 0.0
    io_savings_usd: float = 0.0
    assumed_pricing_tier: str = "standard"
    frequency_per_day: float = 0.0
    calculation_details: Optional[Dict[str, Any]] = None


class RoiRecordCreate(RoiRecordBase):
    experiment_id: uuid.UUID
    connection_id: uuid.UUID


class RoiRecordUpdate(BaseModel):
    estimated_monthly_savings_usd: Optional[float] = None
    compute_savings_usd: Optional[float] = None
    storage_savings_usd: Optional[float] = None
    io_savings_usd: Optional[float] = None
    calculation_details: Optional[Dict[str, Any]] = None


class RoiRecordOut(RoiRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    connection_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RoiSummaryResponse(BaseModel):
    connection_id: uuid.UUID
    total_monthly_savings_usd: float
    total_compute_savings_usd: float
    total_storage_savings_usd: float
    total_io_savings_usd: float
    optimizations_count: int
    roi_breakdowns: List[RoiRecordOut] = Field(default_factory=list)
