from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import strip_html


class RemotiveConnector(Connector):
    name = "remotive"
    endpoint = "https://remotive.com/api/remote-jobs"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        # Remotive asks for conservative usage. Query only the first few targeted keywords per run.
        for keyword in settings.keywords[:3]:
            data = await request_json(
                client,
                self.endpoint,
                params={"search": keyword, "limit": min(settings.max_per_source, 25)},
                headers=default_headers(settings),
            )
            for item in data.get("jobs", []):
                location = item.get("candidate_required_location") or "Worldwide"
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("id") or item.get("url") or item.get("title")),
                    title=item.get("title") or "Untitled",
                    company=item.get("company_name"),
                    url=item.get("url"),
                    location=location,
                    compensation=item.get("salary"),
                    contract_type=item.get("job_type"),
                    remote="remote",
                    japan_ok="yes" if str(location).lower() in {"worldwide", "anywhere"} else "unknown",
                    description=strip_html(item.get("description")),
                    published_at=item.get("publication_date"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs
