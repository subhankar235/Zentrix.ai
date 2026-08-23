"""Deterministic recommendation generation from persisted diagnoses."""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection import DatabaseConnection
from app.models.diagnosis import Diagnosis
from app.models.experiment import OptimizationExperiment
from app.models.telemetry import QueryMetric
from app.schemas.diagnosis import RecommendationOut


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_FROM_TABLE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_$]*)", re.IGNORECASE)
_WHERE_COLUMN = re.compile(
    r"\bwhere\s+(?:[A-Za-z_][A-Za-z0-9_$]*\.)?([A-Za-z_][A-Za-z0-9_$]*)\s*(?:=|>|<|\blike\b|\bin\b)\s*",
    re.IGNORECASE,
)


def _quoted_identifier(value: str | None) -> str | None:
    if not value or not _IDENTIFIER.fullmatch(value):
        return None
    # Identifiers are validated before interpolation; keeping them unquoted
    # also matches the strict candidate grammar used by the shadow executor.
    return value


def _candidate_from_query(query_text: str | None) -> tuple[str, str] | None:
    if not query_text or "$" in query_text or ";" in query_text.rstrip(";"):
        return None
    table_match = _FROM_TABLE.search(query_text)
    column_match = _WHERE_COLUMN.search(query_text)
    table = _quoted_identifier(table_match.group(1) if table_match else None)
    column = _quoted_identifier(column_match.group(1) if column_match else None)
    if not table or not column:
        return None
    index_name = "zentrix_idx_" + hashlib.sha256(f"{table}:{column}".encode()).hexdigest()[:12]
    return table, f"CREATE INDEX CONCURRENTLY {index_name} ON {table} ({column});"


async def _top_query(connection_id: uuid.UUID, db: AsyncSession) -> QueryMetric | None:
    statement = (
        select(QueryMetric)
        .where(
            QueryMetric.connection_id == connection_id,
            QueryMetric.query_text.is_not(None),
            or_(QueryMetric.query_text.ilike("select%"), QueryMetric.query_text.ilike("with%")),
        )
        .order_by(QueryMetric.total_exec_time.desc())
        .limit(1)
    )
    return await db.scalar(statement)


async def recommendations_for_diagnosis(
    diagnosis: Diagnosis,
    db: AsyncSession,
) -> list[RecommendationOut]:
    """Build only actionable candidates supported by the diagnosis evidence."""
    cause = diagnosis.primary_root_cause.upper()
    plan: dict[str, Any] = diagnosis.validation_plan or {}
    affected = plan.get("affected_object")
    table = _quoted_identifier(str(affected).split(".")[-1] if affected not in {None, "database"} else None)

    candidate_type: str | None = None
    title: str | None = None
    candidate_sql: str | None = None
    predicted_impact: str | None = None
    risk = "Low"

    if cause in {"STALE_STATISTICS", "CARDINALITY_MISESTIMATION", "PLAN_FLIP"}:
        candidate_type = "STATISTICS"
        title = f"Refresh planner statistics{f' for {table}' if table else ''}"
        candidate_sql = f"ANALYZE {table};" if table else "ANALYZE;"
        predicted_impact = "May improve cardinality estimates and stabilize query plans."
    elif cause in {"VACUUM_LAG", "BLOAT"}:
        candidate_type = "VACUUM"
        title = f"Vacuum and analyze{f' {table}' if table else ' the affected relation'}"
        candidate_sql = f"VACUUM ANALYZE {table};" if table else None
        predicted_impact = "May reduce dead-tuple pressure and refresh planner statistics."
        risk = "Medium"
    elif cause == "INDEX_MISSING":
        query = await _top_query(diagnosis.connection_id, db)
        candidate = _candidate_from_query(query.query_text if query else None)
        if candidate:
            table, candidate_sql = candidate
            candidate_type = "INDEX"
            title = f"Add a selective index on {table}"
            predicted_impact = "May reduce sequential scans for the observed filtered workload."
            risk = "Medium"

    if not candidate_type or not title or not candidate_sql or not predicted_impact:
        return []

    recommendation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"zentrix:recommendation:{diagnosis.id}:{candidate_sql}",
    )
    experiment = await db.scalar(
        select(OptimizationExperiment)
        .where(
            OptimizationExperiment.diagnosis_id == diagnosis.id,
            OptimizationExperiment.candidate_sql == candidate_sql,
        )
        .order_by(OptimizationExperiment.created_at.desc())
        .limit(1)
    )
    uncertainty = round(max(0.0, min(100.0, (1.0 - diagnosis.confidence) * 100.0)), 1)
    return [
        RecommendationOut(
            id=recommendation_id,
            diagnosis_id=diagnosis.id,
            connection_id=diagnosis.connection_id,
            diagnosis_title=diagnosis.title,
            primary_root_cause=cause,
            type=candidate_type,
            title=title,
            rationale=(
                f"Generated from the persisted {cause} diagnosis and its live PostgreSQL evidence. "
                "The candidate must pass shadow replay and policy verification before approval."
            ),
            predicted_impact=predicted_impact,
            uncertainty_pct=uncertainty,
            risk=risk,
            candidate_sql=candidate_sql,
            experiment_id=experiment.id if experiment else None,
        )
    ]


async def recommendations_for_connection(
    connection_id: uuid.UUID | None,
    db: AsyncSession,
) -> list[RecommendationOut]:
    statement = select(Diagnosis).order_by(Diagnosis.created_at.desc())
    if connection_id:
        statement = statement.where(Diagnosis.connection_id == connection_id)
    diagnoses = (await db.scalars(statement)).all()
    recommendations: list[RecommendationOut] = []
    for diagnosis in diagnoses:
        recommendations.extend(await recommendations_for_diagnosis(diagnosis, db))
    return recommendations


async def recommendations_for_user(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[RecommendationOut]:
    statement = (
        select(Diagnosis)
        .join(DatabaseConnection, DatabaseConnection.id == Diagnosis.connection_id)
        .where(DatabaseConnection.user_id == user_id)
        .order_by(Diagnosis.created_at.desc())
    )
    diagnoses = (await db.scalars(statement)).all()
    recommendations: list[RecommendationOut] = []
    for diagnosis in diagnoses:
        recommendations.extend(await recommendations_for_diagnosis(diagnosis, db))
    return recommendations
