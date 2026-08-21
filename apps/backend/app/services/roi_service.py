"""Feature 4 Deterministic Cost-to-Dollar ROI Translation Service.

Calculates dollar financial impact (compute, I/O, storage, and total monthly savings)
deterministically from verified, measured experiment deltas using transparent pricing
models (no ML, no LLM hallucinations).

Reference: ARCHITECTURE.md §4 & PRD.md §5 Feature 4, §13.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.experiment import OptimizationExperiment
from app.models.roi import RoiRecord
from app.schemas.roi import RoiRecordOut, RoiSummaryResponse

logger = get_logger(__name__)

# Standard cloud provider reference pricing catalog
PRICING_CATALOG: dict[str, dict[str, Any]] = {
    "aws_rds_standard": {
        "name": "AWS RDS PostgreSQL (db.r6g.xlarge baseline)",
        "cpu_cost_per_hour_usd": 0.0416,  # ~$0.0416 per vCPU-hr
        "io_cost_per_million_reads_usd": 0.20,  # $0.20 per million I/O requests
        "storage_cost_per_gb_month_usd": 0.115,  # $0.115/GB-mo GP3
        "is_configured": True,
    },
    "neon_serverless": {
        "name": "Neon Serverless Postgres (Compute Unit)",
        "cpu_cost_per_hour_usd": 0.0350,  # ~$0.035 per CU-hr
        "io_cost_per_million_reads_usd": 0.15,
        "storage_cost_per_gb_month_usd": 0.100,
        "is_configured": True,
    },
    "gcp_cloud_sql": {
        "name": "GCP Cloud SQL PostgreSQL (db-custom)",
        "cpu_cost_per_hour_usd": 0.0413,
        "io_cost_per_million_reads_usd": 0.20,
        "storage_cost_per_gb_month_usd": 0.120,
        "is_configured": True,
    },
    "standard": {
        "name": "Standard Reference Pricing",
        "cpu_cost_per_hour_usd": 0.0400,
        "io_cost_per_million_reads_usd": 0.20,
        "storage_cost_per_gb_month_usd": 0.115,
        "is_configured": True,
    },
}

DAYS_PER_MONTH = 30.4167


def get_pricing_tier(tier_name: str | None) -> dict[str, Any]:
    """Retrieve pricing tier details with strict 'not configured' fallback."""
    key = (tier_name or "standard").strip().lower()
    if key in PRICING_CATALOG:
        return PRICING_CATALOG[key]

    return {
        "name": f"Unknown Tier ({tier_name})",
        "cpu_cost_per_hour_usd": 0.0,
        "io_cost_per_million_reads_usd": 0.0,
        "storage_cost_per_gb_month_usd": 0.0,
        "is_configured": False,
    }


def compute_deterministic_roi(
    baseline_cpu_seconds: float,
    candidate_cpu_seconds: float,
    baseline_io_reads: float,
    candidate_io_reads: float,
    frequency_per_day: float,
    pricing_tier: str = "standard",
    index_storage_mb: float = 0.0,
    custom_pricing: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Pure deterministic calculation of monthly dollar ROI from measured metrics.

    Formulas:
    - Monthly Calls = frequency_per_day * 30.4167
    - Compute Savings = Delta CPU Seconds * Monthly Calls * (Hourly Rate / 3600)
    - IO Savings = Delta IO Reads * Monthly Calls * (IO Rate / 1,000,000)
    - Storage Cost = (Index MB / 1024) * Storage Rate
    - Total Monthly Savings = Compute Savings + IO Savings - Storage Cost
    """
    tier_info = get_pricing_tier(pricing_tier)
    if custom_pricing:
        cpu_rate = float(custom_pricing.get("cpu_cost_per_hour_usd", tier_info["cpu_cost_per_hour_usd"]))
        io_rate = float(custom_pricing.get("io_cost_per_million_reads_usd", tier_info["io_cost_per_million_reads_usd"]))
        storage_rate = float(custom_pricing.get("storage_cost_per_gb_month_usd", tier_info["storage_cost_per_gb_month_usd"]))
        is_configured = True
    else:
        cpu_rate = tier_info["cpu_cost_per_hour_usd"]
        io_rate = tier_info["io_cost_per_million_reads_usd"]
        storage_rate = tier_info["storage_cost_per_gb_month_usd"]
        is_configured = tier_info["is_configured"]

    if not is_configured:
        return {
            "estimated_monthly_savings_usd": 0.0,
            "compute_savings_usd": 0.0,
            "storage_savings_usd": 0.0,
            "io_savings_usd": 0.0,
            "assumed_pricing_tier": pricing_tier,
            "is_cost_model_configured": False,
            "calculation_details": {
                "status": "COST_MODEL_NOT_CONFIGURED",
                "message": f"Pricing tier '{pricing_tier}' has no configured pricing parameters.",
            },
        }

    monthly_calls = max(0.0, frequency_per_day) * DAYS_PER_MONTH

    # 1. Compute savings
    delta_cpu = max(0.0, baseline_cpu_seconds - candidate_cpu_seconds)
    compute_savings = (delta_cpu * monthly_calls * (cpu_rate / 3600.0))

    # 2. IO savings
    delta_io = max(0.0, baseline_io_reads - candidate_io_reads)
    io_savings = (delta_io * monthly_calls * (io_rate / 1_000_000.0))

    # 3. Storage overhead
    storage_gb = max(0.0, index_storage_mb) / 1024.0
    storage_cost = storage_gb * storage_rate

    # Total savings
    total_savings = round(max(0.0, compute_savings + io_savings - storage_cost), 2)
    comp_rounded = round(compute_savings, 2)
    io_rounded = round(io_savings, 2)
    storage_rounded = round(storage_cost, 2)

    return {
        "estimated_monthly_savings_usd": total_savings,
        "compute_savings_usd": comp_rounded,
        "storage_savings_usd": storage_rounded,
        "io_savings_usd": io_rounded,
        "assumed_pricing_tier": pricing_tier,
        "frequency_per_day": frequency_per_day,
        "is_cost_model_configured": True,
        "calculation_details": {
            "monthly_executions": round(monthly_calls),
            "delta_cpu_seconds_per_query": round(delta_cpu, 4),
            "delta_io_reads_per_query": round(delta_io, 1),
            "index_storage_gb": round(storage_gb, 4),
            "rates_applied": {
                "cpu_cost_per_hour_usd": cpu_rate,
                "io_cost_per_million_reads_usd": io_rate,
                "storage_cost_per_gb_month_usd": storage_rate,
            },
            "formula": "(delta_cpu * calls * rate/3600) + (delta_io * calls * rate/1M) - (storage_gb * rate)",
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


class RoiService:
    """Application Service managing deterministic ROI translation and persistence."""

    async def calculate_and_save_experiment_roi(
        self,
        experiment_id: uuid.UUID,
        db: AsyncSession,
        pricing_tier: str = "standard",
        frequency_per_day: float = 100_000.0,
        custom_pricing: Mapping[str, float] | None = None,
    ) -> RoiRecord:
        """Calculate and persist deterministic ROI from a measured optimization experiment."""
        exp = await db.scalar(
            select(OptimizationExperiment).where(OptimizationExperiment.id == experiment_id)
        )
        if not exp:
            raise LookupError(f"Optimization experiment {experiment_id} not found")

        # Measured deltas from experiment record
        base_cpu = float(exp.baseline_cpu)
        cand_cpu = float(exp.candidate_cpu)
        base_io = float(exp.baseline_io)
        cand_io = float(exp.candidate_io)

        calc = compute_deterministic_roi(
            baseline_cpu_seconds=base_cpu,
            candidate_cpu_seconds=cand_cpu,
            baseline_io_reads=base_io,
            candidate_io_reads=cand_io,
            frequency_per_day=frequency_per_day,
            pricing_tier=pricing_tier,
            index_storage_mb=10.0 if "INDEX" in exp.strategy else 0.0,
            custom_pricing=custom_pricing,
        )

        now = datetime.now(timezone.utc)

        # Check existing RoiRecord
        existing = await db.scalar(
            select(RoiRecord).where(RoiRecord.experiment_id == experiment_id)
        )
        if existing:
            existing.estimated_monthly_savings_usd = calc["estimated_monthly_savings_usd"]
            existing.compute_savings_usd = calc["compute_savings_usd"]
            existing.storage_savings_usd = calc["storage_savings_usd"]
            existing.io_savings_usd = calc["io_savings_usd"]
            existing.assumed_pricing_tier = calc["assumed_pricing_tier"]
            existing.frequency_per_day = frequency_per_day
            existing.calculation_details = calc["calculation_details"]
            roi_record = existing
        else:
            roi_record = RoiRecord(
                experiment_id=exp.id,
                connection_id=exp.connection_id,
                estimated_monthly_savings_usd=calc["estimated_monthly_savings_usd"],
                compute_savings_usd=calc["compute_savings_usd"],
                storage_savings_usd=calc["storage_savings_usd"],
                io_savings_usd=calc["io_savings_usd"],
                assumed_pricing_tier=calc["assumed_pricing_tier"],
                frequency_per_day=frequency_per_day,
                calculation_details=calc["calculation_details"],
            )
            db.add(roi_record)

        # Audit log the ROI calculation
        from app.models.audit import AuditLog
        audit_entry = AuditLog(
            connection_id=exp.connection_id,
            action_type="ROI_CALCULATED",
            target_entity="roi_record",
            target_id=str(exp.id),
            details={
                "estimated_monthly_savings_usd": calc["estimated_monthly_savings_usd"],
                "compute_savings_usd": calc["compute_savings_usd"],
                "io_savings_usd": calc["io_savings_usd"],
                "pricing_tier": calc["assumed_pricing_tier"],
                "frequency_per_day": frequency_per_day,
            },
            timestamp=now,
        )
        db.add(audit_entry)

        await db.commit()
        await db.refresh(roi_record)
        return roi_record

    async def get_connection_roi_summary(
        self,
        connection_id: uuid.UUID,
        db: AsyncSession,
    ) -> RoiSummaryResponse:
        """Fetch aggregated ROI savings and breakdowns for a database connection."""
        stmt = (
            select(RoiRecord)
            .where(RoiRecord.connection_id == connection_id)
            .order_by(RoiRecord.created_at.desc())
        )
        res = await db.execute(stmt)
        records = list(res.scalars().all())

        total_monthly = round(sum(r.estimated_monthly_savings_usd for r in records), 2)
        total_compute = round(sum(r.compute_savings_usd for r in records), 2)
        total_storage = round(sum(r.storage_savings_usd for r in records), 2)
        total_io = round(sum(r.io_savings_usd for r in records), 2)

        return RoiSummaryResponse(
            connection_id=connection_id,
            total_monthly_savings_usd=total_monthly,
            total_compute_savings_usd=total_compute,
            total_storage_savings_usd=total_storage,
            total_io_savings_usd=total_io,
            optimizations_count=len(records),
            roi_breakdowns=[RoiRecordOut.model_validate(r) for r in records],
        )

    async def get_experiment_roi(
        self,
        experiment_id: uuid.UUID,
        db: AsyncSession,
    ) -> RoiRecord | None:
        """Retrieve ROI record for an individual experiment."""
        return await db.scalar(
            select(RoiRecord).where(RoiRecord.experiment_id == experiment_id)
        )


roi_service = RoiService()
