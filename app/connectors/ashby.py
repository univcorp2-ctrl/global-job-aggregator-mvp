from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import compact, strip_html


class AshbyConnector(Connector):
    name = "ashby"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for board in settings.ashby_boards:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
            try:
                data = await request_json(
                    client,
                    url,
                    params={"includeCompensation": "true"},
                    headers=default_headers(settings),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("jobs", []):
                location = item.get("location") or _address(item)
                compensation = _compensation(item)
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("jobUrl") or item.get("applyUrl") or item.get("title")),
                    title=item.get("title") or "Untitled",
                    company=board,
                    url=item.get("jobUrl") or item.get("applyUrl"),
                    location=location,
                    compensation=compensation,
                    contract_type=item.get("employmentType") or item.get("department"),
                    remote="remote" if item.get("isRemote") else compact(item.get("workplaceType")),
                    japan_ok="yes" if item.get("isRemote") else "unknown",
                    description=strip_html(item.get("descriptionPlain") or item.get("descriptionHtml")),
                    published_at=item.get("publishedAt"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


def _address(item: dict) -> str | None:
    postal = ((item.get("address") or {}).get("postalAddress") or {})
    parts = [postal.get("addressLocality"), postal.get("addressRegion"), postal.get("addressCountry")]
    text = ", ".join(str(part) for part in parts if part)
    return text or None


def _compensation(item: dict) -> str | None:
    compensation = item.get("compensation") or {}
    if isinstance(compensation, dict):
        for key in ["compensationTierSummary", "scrapeableCompensationSalarySummary"]:
            if compensation.get(key):
                return str(compensation[key])
    for key in ["compensationTierSummary", "scrapeableCompensationSalarySummary"]:
        if item.get(key):
            return str(item[key])
    return None
