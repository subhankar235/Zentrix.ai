"""Deterministic recommendation generation from persisted diagnoses."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection import DatabaseConnection
from app.models.diagnosis import Diagnosis
from app.models.experiment import OptimizationExperiment
from app.models.telemetry import QueryMetric
from app.models.telemetry import TableMetric
from app.schemas.diagnosis import RecommendationOut


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_FROM_TABLE = re.compile(
    r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?)",
    re.IGNORECASE,
)
_WHERE_COLUMN = re.compile(
    r"(?:\bwhere\b|\band\b|\bor\b)\s+(?:[A-Za-z_][A-Za-z0-9_$]*\.)?"
    r"([A-Za-z_][A-Za-z0-9_$]*)\s*(?:=|>|<|<=|>=|<>|!=|\blike\b|\bin\b)",
    re.IGNORECASE,
)
_ORDER_COLUMN = re.compile(
    r"\border\s+by\s+(?:[A-Za-z_][A-Za-z0-9_$]*\.)?"
    r"([A-Za-z_][A-Za-z0-9_$]*)",
    re.IGNORECASE,
)
_UTILITY_ONLY_QUERY = re.compile(r"^\s*(?:select|with)\s+\$\d+(?:\s*;)?\s*$", re.IGNORECASE)
_POSTGRES_INTERNAL_FUNCTION = re.compile(r"\bpg_[a-z0-9_]+\s*\(", re.IGNORECASE)

# These are control-plane tables, not relations from a monitored customer DB.
# They can appear in old seeded telemetry and must never become remediation
# targets for a customer database recommendation.
_CONTROL_PLANE_TABLES = {
    "users",
    "database_connections",
    "query_metrics",
    "table_metrics",
    "plan_metrics",
    "diagnoses",
    "evidence_graph_nodes",
    "evidence_graph_edges",
    "optimization_experiments",
    "model_predictions",
    "bandit_events",
    "audit_logs",
    "approvals",
    "canary_runs",
}
_INTERNAL_QUERY_MARKERS = (
    "pg_catalog.",
    "pg_replication_slots",
    "pg_stat_",
    "information_schema.",
    "pg_toast.",
    "pg_internal.",
    "pg_settings",
    "pg_database",
    "pg_namespace",
    "pg_class",
    "pg_attribute",
    "pg_roles",
    "pg_stat_database",
    "pg_stat_user_tables",
    "current_setting(",
    "version()",
    "neon.",
    "neon_perf_counters",
    "approximate_working_set_size_seconds",
    "get_compute_",
    "pg_ls_waldir",
    "pg_ls_dir",
)


def _is_internal_query(query_text: str | None) -> bool:
    normalized = (query_text or "").lower()
    return bool(_UTILITY_ONLY_QUERY.fullmatch(normalized)) or bool(
        _POSTGRES_INTERNAL_FUNCTION.search(normalized)
    ) or any(
        marker in normalized for marker in _INTERNAL_QUERY_MARKERS
    )


def _quoted_identifier(value: str | None) -> str | None:
    if not value or not _IDENTIFIER.fullmatch(value) or value.lower() in _CONTROL_PLANE_TABLES:
        return None
    # Identifiers are validated before interpolation; keeping them unquoted
    # also matches the strict candidate grammar used by the shadow executor.
    return value


def _query_parts(query_text: str | None) -> tuple[str, list[str], list[str]] | None:
    """Extract only simple identifiers from a read-only query.

    This is intentionally not a SQL parser.  Any query outside this narrow
    grammar is withheld from index generation instead of being guessed at.
    """
    if (
        not query_text
        or "$" in query_text
        or ";" in query_text.rstrip(";")
        or _is_internal_query(query_text)
    ):
        return None
    table_match = _FROM_TABLE.search(query_text)
    table_value = table_match.group(1).split(".")[-1] if table_match else None
    table = _quoted_identifier(table_value)
    where_columns = [
        value for value in (_quoted_identifier(match.group(1)) for match in _WHERE_COLUMN.finditer(query_text))
        if value
    ]
    order_columns = [
        value for value in (_quoted_identifier(match.group(1)) for match in _ORDER_COLUMN.finditer(query_text))
        if value
    ]
    if not table or not where_columns:
        return None
    return table, list(dict.fromkeys(where_columns)), list(dict.fromkeys(order_columns))


def _index_candidates(query_text: str | None, diagnosis_evidence: list[str] | None = None) -> list[dict[str, Any]]:
    parts = _query_parts(query_text)
    if not parts:
        return []
    table, where_columns, order_columns = parts
    candidates: list[dict[str, Any]] = []
    columns = list(dict.fromkeys([*where_columns, *order_columns]))
    variants = [
        ("single-column", columns[:1], "Targets the leading filter predicate."),
    ]
    if len(columns) > 1:
        variants.append(("composite", columns, "Matches the observed filter and ordering columns."))
    for variant, variant_columns, reason in variants:
        if not variant_columns:
            continue
        material = f"{table}:{','.join(variant_columns)}:{variant}"
        index_name = "zentrix_idx_" + hashlib.sha256(material.encode()).hexdigest()[:12]
        sql = f"CREATE INDEX CONCURRENTLY {index_name} ON {table} ({', '.join(variant_columns)});"
        candidates.append({
            "type": "INDEX",
            "title": f"Add {variant} index on {table}",
            "candidate_sql": sql,
            "rollback_sql": f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};",
            "predicted_impact": "May reduce sequential scans and execution latency for the observed read workload.",
            "risk": "Medium",
            "evidence": [
                *(diagnosis_evidence or []),
                reason,
                f"Observed filter column(s): {', '.join(where_columns)}",
            ],
            "score": 76.0 if variant == "composite" else 68.0,
            "requires_hypopg": True,
        })
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


async def _top_query(connection_id: uuid.UUID, db: AsyncSession) -> QueryMetric | None:
    statement = (
        select(QueryMetric)
        .where(
            QueryMetric.connection_id == connection_id,
            QueryMetric.query_text.is_not(None),
            or_(QueryMetric.query_text.ilike("select%"), QueryMetric.query_text.ilike("with%")),
            *[
                ~QueryMetric.query_text.ilike(f"%{marker}%")
                for marker in _INTERNAL_QUERY_MARKERS
            ],
        )
        .order_by(QueryMetric.total_exec_time.desc())
        .limit(100)
    )
    rows = (await db.scalars(statement)).all()
    return next((row for row in rows if not _is_internal_query(row.query_text)), None)


async def _table_evidence(connection_id: uuid.UUID, db: AsyncSession, table: str | None) -> TableMetric | None:
    """Return the newest real telemetry row for one customer relation."""
    if not table:
        return None
    return await db.scalar(
        select(TableMetric)
        .where(
            TableMetric.connection_id == connection_id,
            TableMetric.table_name == table,
            or_(
                TableMetric.capture_source == "live_postgresql",
                TableMetric.capture_source.is_(None),
            ),
        )
        .order_by(TableMetric.timestamp.desc())
        .limit(1)
    )


async def _recover_affected_table(connection_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Recover a relation for older diagnoses that stored only ``database``.

    Early diagnosis records persisted the aggregate metric but not its table.
    Use the latest persisted table snapshots and choose the relation with the
    oldest known analyze timestamp.  This repairs the presentation of those
    records without changing historical diagnosis data or inventing a name.
    """
    rows = (
        await db.scalars(
            select(TableMetric)
            .where(
                TableMetric.connection_id == connection_id,
                or_(
                    TableMetric.capture_source == "live_postgresql",
                    TableMetric.capture_source.is_(None),
                ),
            )
            .order_by(TableMetric.timestamp.desc())
            .limit(500)
        )
    ).all()
    latest_by_table: dict[str, TableMetric] = {}
    for row in rows:
        latest_by_table.setdefault(row.table_name, row)
    if not latest_by_table:
        return None

    def analyze_timestamp(row: TableMetric) -> datetime:
        timestamp = row.last_analyze or row.last_autoanalyze
        if timestamp is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

    return min(latest_by_table.values(), key=analyze_timestamp).table_name


async def recommendations_for_diagnosis(
    diagnosis: Diagnosis,
    db: AsyncSession,
) -> list[RecommendationOut]:
    """Build ranked, deterministic candidates supported by diagnosis evidence.

    Candidate generation is deliberately rule-based.  A candidate is only
    surfaced when it can be validated by the existing shadow/policy pipeline;
    unsupported or low-evidence diagnoses return an explicit empty result.
    """
    cause = diagnosis.primary_root_cause.upper()
    plan: dict[str, Any] = diagnosis.validation_plan or {}
    affected = plan.get("affected_object")
    table = _quoted_identifier(str(affected).split(".")[-1] if affected not in {None, "database"} else None)
    top_query = await _top_query(diagnosis.connection_id, db)
    query_parts = _query_parts(top_query.query_text if top_query else None)
    if not table and query_parts:
        table = query_parts[0]
    if not table and cause in {"STALE_STATISTICS", "CARDINALITY_MISESTIMATION", "PLAN_FLIP", "VACUUM_LAG", "BLOAT"}:
        table = _quoted_identifier(await _recover_affected_table(diagnosis.connection_id, db))
    table_row = await _table_evidence(diagnosis.connection_id, db, table)

    supporting_evidence = plan.get("supporting_evidence") or []
    evidence: list[str] = []
    evidence_tables: list[str] = []
    for item in supporting_evidence:
        if isinstance(item, dict):
            evidence_table = _quoted_identifier(str(item.get("table_name") or ""))
            if evidence_table:
                evidence_tables.append(evidence_table)
            claim = item.get("claim") or item.get("metric")
            value = item.get("value")
            if claim:
                evidence.append(f"{claim}{f' ({value})' if value is not None else ''}")
    for factor in diagnosis.contributing_factors or []:
        if isinstance(factor, dict):
            cause_name = factor.get("cause")
            confidence = factor.get("confidence")
            if cause_name:
                evidence.append(
                    f"Contributing diagnosis: {cause_name}"
                    f"{f' ({float(confidence):.0%} confidence)' if confidence is not None else ''}."
                )
    if top_query and top_query.query_text:
        query_text = top_query.query_text
        evidence.append(
            f"Highest-cost customer query: {query_text[:180]}"
            f" ({top_query.total_exec_time:.1f} ms total execution time)."
        )
    if table_row:
        evidence.append(
            f"Live table telemetry for {table_row.table_name}: "
            f"{table_row.live_tuples:,} live rows, {table_row.dead_tuples:,} dead rows, "
            f"{table_row.dead_tuple_ratio:.1%} dead-tuple ratio."
        )
    if not table and evidence_tables:
        table = evidence_tables[0]
    if not evidence:
        evidence.append(f"Diagnosis confidence: {diagnosis.confidence:.0%}.")

    candidates: list[dict[str, Any]] = []
    if cause in {"STALE_STATISTICS", "CARDINALITY_MISESTIMATION", "PLAN_FLIP"}:
        analyze_timestamp = table_row.last_analyze or table_row.last_autoanalyze if table_row else None
        if analyze_timestamp and analyze_timestamp.tzinfo is None:
            analyze_timestamp = analyze_timestamp.replace(tzinfo=timezone.utc)
        analyze_age = (
            (datetime.now(timezone.utc) - analyze_timestamp).total_seconds() / 3600
            if analyze_timestamp
            else None
        )
        impact = (
            f"Statistics are approximately {analyze_age:.1f} hours old; ANALYZE may improve estimates for {table}."
            if analyze_age is not None and table
            else "Refreshes planner statistics so PostgreSQL can recalculate cardinality estimates."
        )
        candidates.append({
            "type": "STATISTICS",
            "title": f"Refresh planner statistics{f' for {table}' if table else ' for the database'}",
            "candidate_sql": f"ANALYZE {table};" if table else "ANALYZE;",
            "rollback_sql": None,
            "predicted_impact": impact,
            "risk": "Low",
            "evidence": evidence,
            "score": (92.0 if table else 78.0) if cause == "STALE_STATISTICS" else (84.0 if table else 70.0),
            "requires_hypopg": False,
        })
    elif cause in {"VACUUM_LAG", "BLOAT"}:
        if table:
            candidates.append({
                "type": "VACUUM",
                "title": f"Vacuum and analyze {table}",
                "candidate_sql": f"VACUUM ANALYZE {table};",
                "rollback_sql": None,
                "predicted_impact": "May reduce dead-tuple pressure and refresh planner statistics.",
                "risk": "Medium",
                "evidence": evidence + [f"Affected relation: {table}"],
                "score": 89.0,
                "requires_hypopg": False,
            })
    if cause in {"INDEX_MISSING", "BUFFER_PRESSURE", "IO_SATURATION", "TEMP_SPILL"}:
        candidates.extend(_index_candidates(top_query.query_text if top_query else None, evidence))

    if not candidates:
        return []
    uncertainty = round(max(0.0, min(100.0, (1.0 - diagnosis.confidence) * 100.0)), 1)
    candidates.sort(key=lambda item: item["score"], reverse=True)
    output: list[RecommendationOut] = []
    for rank, candidate in enumerate(candidates, start=1):
        candidate_sql = candidate["candidate_sql"]
        recommendation_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"zentrix:recommendation:{diagnosis.id}:{candidate_sql}",
        )
        experiment = await db.scalar(
            select(OptimizationExperiment)
            .where(
                OptimizationExperiment.connection_id == diagnosis.connection_id,
                OptimizationExperiment.candidate_sql == candidate_sql,
            )
            .order_by(OptimizationExperiment.created_at.desc())
            .limit(1)
        )
        output.append(RecommendationOut(
            id=recommendation_id,
            diagnosis_id=diagnosis.id,
            connection_id=diagnosis.connection_id,
            diagnosis_title=diagnosis.title,
            primary_root_cause=cause,
            type=candidate["type"],
            title=candidate["title"],
            rationale=(
                f"Generated from the persisted {cause} diagnosis and its live PostgreSQL evidence. "
                "The candidate must pass HypoPG where applicable, shadow replay, statistical verification, "
                "and policy checks before approval."
            ),
            predicted_impact=candidate["predicted_impact"],
            uncertainty_pct=uncertainty,
            risk=candidate["risk"],
            candidate_sql=candidate_sql,
            table_name=table,
            experiment_id=experiment.id if experiment else None,
            rank=rank,
            score=candidate["score"],
            evidence=candidate["evidence"] or evidence,
            prerequisites=[
                "Read-only PostgreSQL telemetry",
                "Parameter-free replayable query" if candidate["requires_hypopg"] else "Target relation must exist",
                "Shadow replay and policy approval before production execution",
            ],
            rollback_sql=candidate["rollback_sql"],
            requires_hypopg=candidate["requires_hypopg"],
            ml_status="REQUIRED_DURING_SIMULATION",
        ))
    return output


async def recommendations_for_connection(
    connection_id: uuid.UUID | None,
    db: AsyncSession,
) -> list[RecommendationOut]:
    statement = select(Diagnosis).order_by(Diagnosis.created_at.desc())
    if connection_id:
        statement = statement.where(Diagnosis.connection_id == connection_id)
    diagnoses = (await db.scalars(statement)).all()
    recommendations: list[RecommendationOut] = []
    seen_candidates: set[tuple[uuid.UUID, str, str, str]] = set()
    for diagnosis in diagnoses:
        for recommendation in await recommendations_for_diagnosis(diagnosis, db):
            # A connection should show one current recommendation per cause and
            # action.  Repeated diagnosis snapshots are history, not options.
            key = (
                recommendation.connection_id,
                recommendation.primary_root_cause,
                recommendation.type,
                recommendation.candidate_sql,
            )
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            recommendations.append(recommendation)
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
    seen_candidates: set[tuple[uuid.UUID, str, str, str]] = set()
    for diagnosis in diagnoses:
        for recommendation in await recommendations_for_diagnosis(diagnosis, db):
            key = (
                recommendation.connection_id,
                recommendation.primary_root_cause,
                recommendation.type,
                recommendation.candidate_sql,
            )
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            recommendations.append(recommendation)
    return recommendations
