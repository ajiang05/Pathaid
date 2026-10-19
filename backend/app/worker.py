"""Single-process database worker for durable ingestion stages."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import sessionmaker

from .database import SessionLocal
from .extraction import ExtractionProvider, OpenAIExtractionAdapter
from .models import IngestionRun
from .orchestration import Clock, OrchestrationConfig, claim_next_run, utc_now
from .orchestration_stages import process_acquisition_stage, process_extraction_stage, process_validation_stage


LOGGER = logging.getLogger("pathaid.worker")
ProviderFactory = Callable[[], ExtractionProvider]


@dataclass(frozen=True)
class WorkerConfig:
    """Polling settings plus the bounded orchestration policy."""

    poll_seconds: float = 2.0
    lease_seconds: int = 120
    maximum_stage_attempts: int = 3
    retry_base_seconds: int = 5

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Read positive worker settings while keeping retries capped at three."""

        attempts = _positive_int("PATHAID_INGESTION_MAX_ATTEMPTS", 3)
        if attempts > 3:
            raise ValueError("PATHAID_INGESTION_MAX_ATTEMPTS cannot exceed 3")
        return cls(
            poll_seconds=_positive_float("PATHAID_WORKER_POLL_SECONDS", 2.0),
            lease_seconds=_positive_int("PATHAID_WORKER_LEASE_SECONDS", 120),
            maximum_stage_attempts=attempts,
            retry_base_seconds=_positive_int("PATHAID_INGESTION_RETRY_BASE_SECONDS", 5),
        )

    def orchestration(self) -> OrchestrationConfig:
        """Return the stage policy consumed by orchestration helpers."""

        return OrchestrationConfig(
            lease_seconds=self.lease_seconds,
            maximum_stage_attempts=self.maximum_stage_attempts,
            retry_base_seconds=self.retry_base_seconds,
        )


def process_next_run(
    session_factory: sessionmaker = SessionLocal,
    *,
    worker_id: str | None = None,
    config: WorkerConfig = WorkerConfig(),
    provider_factory: ProviderFactory = OpenAIExtractionAdapter,
    clock: Clock = utc_now,
) -> bool:
    """Claim and execute one durable stage, returning whether work was found."""

    identity = worker_id or f"{socket.gethostname()}-{os.getpid()}"
    policy = config.orchestration()
    with session_factory() as db:
        lease = claim_next_run(db, identity, policy, clock=clock)
        if lease is None:
            return False
        run = db.get(IngestionRun, lease.run_id)
        # Constructing the OpenAI client is deliberately deferred until the
        # extraction stage, so other stages and offline operation need no key.
        if run.state == "acquiring":
            process_acquisition_stage(db, lease, policy, clock=clock)
        elif run.state == "extracting":
            process_extraction_stage(db, lease, provider_factory(), policy, clock=clock)
        elif run.state == "validating":
            process_validation_stage(db, lease, policy, clock=clock)
        return True


def run_forever(
    session_factory: sessionmaker = SessionLocal,
    *,
    worker_id: str | None = None,
    config: WorkerConfig,
    provider_factory: ProviderFactory = OpenAIExtractionAdapter,
) -> None:
    """Poll serially, keeping default concurrency bounded to one process."""

    while True:
        worked = process_next_run(
            session_factory,
            worker_id=worker_id,
            config=config,
            provider_factory=provider_factory,
        )
        if not worked:
            time.sleep(config.poll_seconds)


def main() -> None:
    """Run one stage with --once or continuously until interrupted."""

    parser = argparse.ArgumentParser(description="Process Pathaid ingestion runs")
    parser.add_argument("--once", action="store_true", help="Process at most one due stage and exit")
    parser.add_argument("--worker-id", help="Stable diagnostic worker identifier")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        config = WorkerConfig.from_env()
        if arguments.once:
            process_next_run(worker_id=arguments.worker_id, config=config)
        else:
            run_forever(worker_id=arguments.worker_id, config=config)
    except KeyboardInterrupt:
        LOGGER.info("worker_stopped")


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer worker setting without echoing its value."""

    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(name: str, default: float) -> float:
    """Read a positive numeric worker setting without echoing its value."""

    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a positive number") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


if __name__ == "__main__":
    main()
