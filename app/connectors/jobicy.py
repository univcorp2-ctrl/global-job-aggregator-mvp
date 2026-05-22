from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import strip_html


class JobicyConnector(Connector):
    name = "jobicy"
    endpoint = "https://jobicy.com/api/v2/remote-jobs"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords:
            data = await request_json(
                client,
                self.endpoint,
                params={"count": min(settings.max_per_source, 100), "tag": keyword},
                headers=default_headers(settings),
            )
            for item in data.get("jobs", []):
                salary = _salary(item)
                geo = item.get("jobGeo") or "Anywhere"
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("id") or item.get("url") or item.get("jobTitle")),
                    title=item.get("jobTitle") or "Untitled",
                    company=item.get("companyName"),
                    url=item.get("url"),
                    location=geo,
                    compensation=salary,
                    contract_type=item.get("jobType"),
                    remote="remote",
                    japan_ok="yes" if str(geo).lower() in {"anywhere", "worldwide"} else "unknown",
                    description=strip_html(item.get("jobDescription") or item.get("jobExcerpt")),
                    published_at=item.get("pubDate"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


def _salary(item: dict) -> str | None:
    minimum = item.get("salaryMin")
    maximum = item.get("salaryMax")
    currency = item.get("salaryCurrency") or "USD"
    period = item.get("salaryPeriod") or "year"
    if minimum and maximum:
        return f"{currency} {minimum:,} - {maximum:,} per {period}"
    if minimum:
        return f"{currency} {minimum:,}+ per {period}"
    if maximum:
        return f"up to {currency} {maximum:,} per {period}"
    return None
