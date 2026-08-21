"""Unified CLI Dispatcher for Zentrix Background Workers.

Enables a single container image (worker.Dockerfile) to run any of the four
independent worker processes via command-line argument:
- telemetry: app.workers.telemetry_collector
- canary: app.workers.canary_monitor
- retrain: app.workers.retrain_worker
- shadow: app.workers.shadow_lab_worker

Reference: ARCHITECTURE.md §4, §6 & PRD.md §13.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.logging import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zentrix Background Worker Process Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "worker_type",
        choices=["telemetry", "canary", "retrain", "shadow"],
        help="Type of background worker process to run",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Custom polling interval in seconds",
    )
    return parser.parse_args()


async def run_selected_worker(worker_type: str, interval: int | None = None) -> None:
    """Dispatch to selected worker main loop."""
    logger.info(f"Launching Zentrix worker process: '{worker_type}'")

    if worker_type == "telemetry":
        from app.workers.telemetry_collector import main as telemetry_main
        await telemetry_main()
    elif worker_type == "canary":
        from app.workers.canary_monitor import main as canary_main
        await canary_main()
    elif worker_type == "retrain":
        from app.workers.retrain_worker import main as retrain_main
        await retrain_main()
    elif worker_type == "shadow":
        from app.workers.shadow_lab_worker import main as shadow_main
        await shadow_main()
    else:
        logger.error(f"Unknown worker type: {worker_type}")
        sys.exit(1)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run_selected_worker(args.worker_type, args.interval))
    except KeyboardInterrupt:
        logger.info(f"Worker '{args.worker_type}' shutting down cleanly on SIGINT")


if __name__ == "__main__":
    main()
