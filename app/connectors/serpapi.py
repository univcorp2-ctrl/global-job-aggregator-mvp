from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import Connector, default_headers, polite_sleep, request_json
from app.models import NormalizedJob
from app.utils import join_values, strip_html


class SerpApiConnector(Connector):
    name = "serpapi"
    endpoint = "https://serpapi.com/search.json"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        if not settings.serpapi_api_key:
            return []
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords[:5]:
            data = await request_json(
                client,
                self.endpoint,
                params={
                    "engine": "google_jobs",
                    "q": f"{keyword} remote contract",
                    "hl": "en",
                    "gl": "us",
                    "api_key": settings.serpapi_api_key,
                    "no_cache": "false",
                },
                headers=default_headers(settings),
            )
            for item in data.get("jobs_results", []):
                extensions = item.get("extensions") or []
                detected = item.get("detected_extensions") or {}
                apply_options = item.get("apply_options") or []
                url = (apply_options[0] or {}).get("link") if apply_options else item.get("share_link")
                job = NormalizedJob(
                    source=self.name,
                    external_id=str(item.get("job_id") or item.get("share_link") or item.get("title")),
                    title=item.get("title") or "Untitled",
                    company=item.get("company_name"),
                    url=url,
                    location=item.get("location"),
                    compensation=join_values([ext for ext in extensions if "$" in str(ext)]),
                    contract_type=detected.get("schedule_type") or join_values(extensions),
                    remote="remote" if "remote" in str(item.get("location", "")).lower() else "unknown",
                    japan_ok="unknown",
                    description=strip_html(item.get("description")),
                    published_at=detected.get("posted_at"),
                    raw=item,
                )
                jobs.append(job)
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs
