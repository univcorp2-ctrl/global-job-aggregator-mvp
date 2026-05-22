from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import safe_get, strip_html


class LeverConnector(Connector):
    name = "lever"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for company in settings.lever_companies:
            url = f"https://api.lever.co/v0/postings/{company}"
            try:
                data = await request_json(
                    client,
                    url,
                    params={"mode": "json"},
                    headers=default_headers(settings),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("items", []):
                location = safe_get(item, ["categories", "location"])
                team = safe_get(item, ["categories", "team"])
                commitment = safe_get(item, ["categories", "commitment"])
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("id") or item.get("hostedUrl") or item.get("text")),
                    title=item.get("text") or "Untitled",
                    company=company,
                    url=item.get("hostedUrl") or item.get("applyUrl"),
                    location=location,
                    compensation=None,
                    contract_type=commitment or team,
                    remote="remote" if "remote" in str(location).lower() else "unknown",
                    japan_ok="yes" if "remote" in str(location).lower() else "unknown",
                    description=strip_html(item.get("descriptionPlain") or item.get("description")),
                    published_at=str(item.get("createdAt")) if item.get("createdAt") else None,
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs
