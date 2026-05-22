from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from typing import Iterable

import httpx

from app.config import Settings
from app.connectors import (
    ArbeitnowConnector,
    AshbyConnector,
    FreelancerConnector,
    GreenhouseConnector,
    HimalayasConnector,
    JobicyConnector,
    LeverConnector,
    RemotiveConnector,
    SerpApiConnector,
)
from app.connectors.base import Connector
from app.db import connect, init_db, record_source_run, source_due, upsert_job
from app.models import NormalizedJob
from app.scoring import enrich_job


def default_connectors() -> list[Connector]:
    return [
        HimalayasConnector(),
        JobicyConnector(),
        ArbeitnowConnector(),
        RemotiveConnector(),
        GreenhouseConnector(),
        LeverConnector(),
        AshbyConnector(),
        SerpApiConnector(),
        FreelancerConnector(),
    ]


@dataclass
class SourceResult:
    source: str
    fetched: int = 0
    saved: int = 0
    skipped: bool = False
    error: str | None = None


@dataclass
class CollectSummary:
    results: list[SourceResult] = field(default_factory=list)

    @property
    def saved_total(self) -> int:
        return sum(result.saved for result in self.results)

    @property
    def fetched_total(self) -> int:
        return sum(result.fetched for result in self.results)

    def as_dict(self) -> dict:
        return {
            "fetched_total": self.fetched_total,
            "saved_total": self.saved_total,
            "results": [result.__dict__ for result in self.results],
        }


def dedupe_jobs(jobs: Iterable[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[tuple[str, str]] = set()
    unique: list[NormalizedJob] = []
    for job in jobs:
        key = (job.source, str(job.external_id))
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


async def collect_all(
    *,
    settings: Settings | None = None,
    connectors: list[Connector] | None = None,
    force: bool = False,
) -> CollectSummary:
    settings = settings or Settings.from_env()
    connectors = connectors or default_connectors()
    init_db(settings.db_path)
    summary = CollectSummary()

    timeout = httpx.Timeout(settings.http_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        with connect(settings.db_path) as conn:
            for connector in connectors:
                cooldown = settings.cooldown_hours.get(connector.name, 6)
                if not force and not source_due(conn, connector.name, cooldown):
                    summary.results.append(SourceResult(source=connector.name, skipped=True))
                    continue
                try:
                    fetched_jobs = dedupe_jobs(await connector.collect(client, settings))
                    saved = 0
                    for job in fetched_jobs:
                        enrich_job(job)
                        if upsert_job(conn, job):
                            saved += 1
                    record_source_run(
                        conn,
                        connector.name,
                        status="success",
                        count=len(fetched_jobs),
                    )
                    summary.results.append(
                        SourceResult(source=connector.name, fetched=len(fetched_jobs), saved=saved)
                    )
                except Exception as exc:  # noqa: BLE001 - collect should continue per source
                    message = f"{type(exc).__name__}: {exc}"
                    record_source_run(
                        conn,
                        connector.name,
                        status="error",
                        count=0,
                        error=message,
                    )
                    summary.results.append(SourceResult(source=connector.name, error=message))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect jobs into SQLite")
    parser.add_argument("--force", action="store_true", help="Ignore source cooldowns")
    return parser.parse_args()


async def amain() -> None:
    args = parse_args()
    summary = await collect_all(force=args.force)
    print(summary.as_dict())


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
