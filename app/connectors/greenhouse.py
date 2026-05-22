from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import join_values, strip_html


class GreenhouseConnector(Connector):
    name = "greenhouse"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for board in settings.greenhouse_boards:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
            try:
                data = await request_json(
                    client,
                    url,
                    params={"content": "true"},
                    headers=default_headers(settings),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("jobs", []):
                location = (item.get("location") or {}).get("name")
                departments = [dept.get("name") for dept in item.get("departments", []) if dept.get("name")]
                offices = [office.get("location") or office.get("name") for office in item.get("offices", [])]
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("id") or item.get("absolute_url")),
                    title=item.get("title") or "Untitled",
                    company=board,
                    url=item.get("absolute_url"),
                    location=location or join_values(offices),
                    compensation=None,
                    contract_type=join_values(departments),
                    remote="remote" if "remote" in str(location).lower() else "unknown",
                    japan_ok=_japan_ok(location, offices),
                    description=strip_html(item.get("content")),
                    published_at=item.get("updated_at"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


def _japan_ok(location: str | None, offices: list[str]) -> str:
    text = f"{location or ''} {' '.join(str(item) for item in offices)}".lower()
    if "remote" in text or "worldwide" in text or "japan" in text:
        return "yes"
    return "unknown"
