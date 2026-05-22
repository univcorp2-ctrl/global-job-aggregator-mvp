from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import strip_html


class FreelancerConnector(Connector):
    name = "freelancer"
    endpoint = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        if not settings.freelancer_oauth_token:
            return []
        jobs: list[NormalizedJob] = []
        headers = default_headers(settings)
        headers["Authorization"] = f"Bearer {settings.freelancer_oauth_token}"
        for keyword in settings.keywords[:5]:
            data = await request_json(
                client,
                self.endpoint,
                params={"query": keyword, "limit": min(settings.max_per_source, 50), "full_description": "true"},
                headers=headers,
            )
            result = data.get("result") or data
            for item in result.get("projects", result.get("items", [])):
                budget = item.get("budget") or {}
                currency = (budget.get("currency") or {}).get("code") or "USD"
                minimum = budget.get("minimum")
                maximum = budget.get("maximum")
                compensation = None
                if minimum and maximum:
                    compensation = f"{currency} {minimum} - {maximum}"
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("id") or item.get("seo_url") or item.get("title")),
                    title=item.get("title") or "Untitled",
                    company=str(item.get("owner_id")) if item.get("owner_id") else None,
                    url=f"https://www.freelancer.com/projects/{item.get('seo_url')}" if item.get("seo_url") else None,
                    location=None,
                    compensation=compensation,
                    contract_type=item.get("type"),
                    remote="remote",
                    japan_ok="unknown",
                    description=strip_html(item.get("description")),
                    published_at=str(item.get("submitdate")) if item.get("submitdate") else None,
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs
