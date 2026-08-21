import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.workers.__main__ import parse_args, run_selected_worker
from app.workers.canary_monitor import monitor_active_canaries_once, run_canary_worker
from app.workers.retrain_worker import run_retrain_worker
from app.workers.shadow_lab_worker import run_shadow_lab_worker
from app.workers.telemetry_collector import run_worker as run_telemetry_worker


@pytest_asyncio.fixture
async def worker_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_cli_argument_parser():
    with patch.object(sys, "argv", ["app.workers", "telemetry"]):
        args = parse_args()
        assert args.worker_type == "telemetry"

    with patch.object(sys, "argv", ["app.workers", "canary", "--interval", "5"]):
        args = parse_args()
        assert args.worker_type == "canary"
        assert args.interval == 5

    with patch.object(sys, "argv", ["app.workers", "retrain"]):
        args = parse_args()
        assert args.worker_type == "retrain"

    with patch.object(sys, "argv", ["app.workers", "shadow"]):
        args = parse_args()
        assert args.worker_type == "shadow"


@pytest.mark.asyncio
async def test_canary_worker_standalone_lifecycle(worker_db):
    stop_event = asyncio.Event()

    # Set stop event after a brief moment
    async def stop_soon():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(stop_soon())
    # Should run and exit cleanly without error
    await run_canary_worker(stop_event=stop_event, poll_interval=1, session_factory=worker_db)
    assert stop_event.is_set()


@pytest.mark.asyncio
async def test_retrain_worker_standalone_lifecycle(worker_db):
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(stop_soon())
    await run_retrain_worker(stop_event=stop_event, poll_interval=1, session_factory=worker_db)
    assert stop_event.is_set()


@pytest.mark.asyncio
async def test_shadow_lab_worker_standalone_lifecycle(worker_db):
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(stop_soon())
    await run_shadow_lab_worker(stop_event=stop_event, poll_interval=1, session_factory=worker_db)
    assert stop_event.is_set()


@pytest.mark.asyncio
async def test_telemetry_worker_standalone_lifecycle(worker_db):
    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(stop_soon())
    await run_telemetry_worker(stop_event=stop_event, poll_interval=1, session_factory=worker_db)
    assert stop_event.is_set()
