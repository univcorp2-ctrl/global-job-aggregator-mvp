from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import join_values, strip_html


class HimalayasConnector(Connector):
    name = "himalayas"
    endpoint = "https://himalayas.app/jobs/api/search"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords:
            data = await request_json(
                client,
                self.endpoint,
                params={"q": keyword, "sort": "recent", "page": 1},
                headers=default_headers(settings),
            )
            for item in data.get("jobs", []):
                locations = item.get("locationRestrictions") or []
                salary = _salary(item)
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("guid") or item.get("applicationLink") or item.get("title")),
                    title=item.get("title") or "Untitled",
                    company=item.get("companyName"),
                    url=item.get("applicationLink"),
                    location=join_values(locations) or "Worldwide",
                    compensation=salary,
                    contract_type=item.get("employmentType"),
                    remote="remote",
                    japan_ok=_japan_ok(locations),
                    description=strip_html(item.get("description") or item.get("excerpt")),
                    published_at=item.get("pubDate"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


def _salary(item: dict) -> str | None:
    min_salary = item.get("minSalary")
    max_salary = item.get("maxSalary")
    currency = item.get("currency") or "USD"
    if min_salary and max_salary:
        return f"{currency} {min_salary:,} - {max_salary:,}"
    if min_salary:
        return f"{currency} {min_salary:,}+"
    if max_salary:
        return f"up to {currency} {max_salary:,}"
    return None


def _japan_ok(locations: list[str]) -> str:
    if not locations:
        return "yes"
    lowered = ",".join(locations).lower()
    if "japan" in lowered or "jp" in lowered or "worldwide" in lowered:
        return "yes"
    return "unknown"
