from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, request_json
from app.models import NormalizedJob
from app.utils import join_values, strip_html


class ArbeitnowConnector(Connector):
    name = "arbeitnow"
    endpoint = "https://www.arbeitnow.com/api/job-board-api"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        data = await request_json(client, self.endpoint, headers=default_headers(settings))
        jobs: list[NormalizedJob] = []
        for item in data.get("data", data.get("items", [])):
            tags = item.get("tags") or []
            job_types = item.get("job_types") or []
            title = item.get("title") or "Untitled"
            description = strip_html(item.get("description"))
            searchable = f"{title} {description} {' '.join(tags)}".lower()
            if not any(keyword.lower() in searchable for keyword in settings.keywords):
                continue
            job = NormalizedJob(
                source=self.name,
                external_id=str(item.get("slug") or item.get("url") or title),
                title=title,
                company=item.get("company_name"),
                url=item.get("url"),
                location=item.get("location"),
                compensation=None,
                contract_type=join_values(job_types),
                remote="remote" if item.get("remote") else "unknown",
                japan_ok="unknown",
                required_skills=[str(tag) for tag in tags],
                description=description,
                published_at=str(item.get("created_at")) if item.get("created_at") else None,
                raw=item,
            )
            jobs.append(job)
            if len(jobs) >= settings.max_per_source:
                return jobs
        return jobs
