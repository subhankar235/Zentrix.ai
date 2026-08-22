"""Controlled PostgreSQL fault injection for the Database Fault Laboratory.

These actions are intentionally explicit and are only suitable for an
isolated lab database.  The monitored-database tools remain read-only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable


class FaultType(StrEnum):
    STALE_STATISTICS = "STALE_STATISTICS"
    PLAN_FLIP = "PLAN_FLIP"
    CARDINALITY_MISESTIMATION = "CARDINALITY_MISESTIMATION"
    LOCK_CONTENTION = "LOCK_CONTENTION"
    VACUUM_LAG = "VACUUM_LAG"
    INDEX_MISSING = "INDEX_MISSING"
    INDEX_UNUSED = "INDEX_UNUSED"
    IO_SATURATION = "IO_SATURATION"
    BUFFER_PRESSURE = "BUFFER_PRESSURE"


@dataclass(frozen=True)
class FaultScenario:
    """A reproducible fault definition and its classifier labels."""

    name: str
    labels: tuple[str, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)


FAULT_MATRIX: dict[str, FaultScenario] = {
    fault.value: FaultScenario(fault.value.lower(), (fault.value,))
    for fault in FaultType
}


def scenario(name: str, **parameters: Any) -> FaultScenario:
    """Return a named matrix scenario with parameter overrides."""
    try:
        base = FAULT_MATRIX[name.upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown fault scenario: {name}") from exc
    return FaultScenario(base.name, base.labels, {**base.parameters, **parameters})


async def apply_fault(connection: Any, fault: FaultScenario) -> dict[str, Any]:
    """Apply one fault to an asyncpg-compatible lab connection.

    The caller owns the lab schema and transaction.  Statements use fixed
    identifiers; configurable values are passed as bound parameters where
    PostgreSQL permits them.
    """
    table = str(fault.parameters.get("table", "fault_lab_orders"))
    if not table.replace("_", "").isalnum() or not table[0].isalpha():
        raise ValueError("Invalid lab table identifier")
    statements: list[str] = []
    if FaultType.STALE_STATISTICS.value in fault.labels:
        statements.append(f"INSERT INTO {table} (customer_id, amount) SELECT 999999, 1 FROM generate_series(1, 1000)")
        statements.append("ALTER TABLE " + table + " ALTER COLUMN customer_id SET STATISTICS 1")
    elif FaultType.PLAN_FLIP.value in fault.labels:
        statements.append(f"INSERT INTO {table} (customer_id, amount) SELECT 1000000 + g, g FROM generate_series(1, 5000) AS g")
    elif FaultType.CARDINALITY_MISESTIMATION.value in fault.labels:
        statements.append(f"INSERT INTO {table} (customer_id, amount) SELECT 7, g FROM generate_series(1, 10000) AS g")
    elif FaultType.VACUUM_LAG.value in fault.labels:
        statements.append(f"UPDATE {table} SET amount = amount + 1 WHERE id % 2 = 0")
    elif FaultType.INDEX_MISSING.value in fault.labels:
        statements.append(f"DROP INDEX IF EXISTS {table}_customer_id_idx")
    elif FaultType.INDEX_UNUSED.value in fault.labels:
        statements.append(f"CREATE INDEX IF NOT EXISTS {table}_customer_id_idx ON {table} (customer_id)")
    elif FaultType.IO_SATURATION.value in fault.labels or FaultType.BUFFER_PRESSURE.value in fault.labels:
        statements.append(f"SELECT count(*) FROM {table} a CROSS JOIN {table} b")
    elif FaultType.LOCK_CONTENTION.value in fault.labels:
        # The held transaction must remain open; use hold_lock() for that case.
        statements.append(f"SELECT id FROM {table} WHERE id = 1 FOR UPDATE")

    for statement in statements:
        await connection.execute(statement)
    return {"scenario": fault.name, "labels": list(fault.labels), "statements": statements}


async def hold_lock(connection: Any, table: str = "fault_lab_orders", row_id: int = 1) -> None:
    """Acquire a lock and keep the caller's transaction open for contention."""
    if not table.replace("_", "").isalnum() or not table[0].isalpha():
        raise ValueError("Invalid lab table identifier")
    await connection.execute(f"SELECT id FROM {table} WHERE id = $1 FOR UPDATE", row_id)


async def run_scenario(
    connection: Any,
    fault: FaultScenario,
    telemetry_reader: Callable[[Any], Awaitable[list[Mapping[str, Any]]]],
    recorder: Any,
    *,
    workload: Mapping[str, Any] | None = None,
) -> Any:
    """Apply, observe, and persist one labeled fault-lab experiment."""
    await apply_fault(connection, fault)
    telemetry = await telemetry_reader(connection)
    return recorder.record(
        scenario=fault.name,
        labels=fault.labels,
        telemetry=telemetry,
        workload=workload,
        fault_parameters=fault.parameters,
    )
