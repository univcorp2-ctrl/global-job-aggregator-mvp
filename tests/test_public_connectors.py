"""Offline regression tests: public API adapters must not require secrets or auto-apply."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.core import (
    JobicyConnector, RemotiveConnector, RemoshiftConnector,
    Settings, default_connectors,
)


def test_default_connectors_are_read_only_public_sources():
    names = [c.name for c in default_connectors()]
    assert names == ["himalayas", "jobicy", "arbeitnow", "remotive", "remoshift", "freelancer_public"]


def test_remotive_only_retains_attributed_original_links():
    payload = {"jobs": [
        {"id": 1, "title": "Python Automation Contractor", "company_name": "Example Co",
         "url": "https://remotive.com/remote-jobs/software-development/1",
         "candidate_required_location": "Worldwide", "salary": "$85/hr"},
        {"id": 2, "title": "Blocked external mirror", "url": "https://example.org/mirror"}
    ]}
    async def run():
        with patch("app.core.request_json", new=AsyncMock(return_value=payload)) as mock_get:
            jobs = await RemotiveConnector().collect(None, Settings(max_per_source=10))
        assert len(jobs) == 1
        assert jobs[0].japan_ok == "yes"
        assert jobs[0].url.startswith("https://remotive.com/")
        assert mock_get.await_count == 1
    asyncio.run(run())


def test_remoshift_uses_required_canonical_detail_link():
    payload = {"data": [
        {"id": 11, "title": "AI Integration", "company_name": "Sample",
         "detail_url": "https://remoshift.com/jobs/11",
         "apply_url": "https://employer.example/apply", "location": "Anywhere"},
        {"id": 12, "title": "No source link", "apply_url": "https://employer.example/apply"}
    ]}
    async def run():
        with patch("app.core.request_json", new=AsyncMock(return_value=payload)):
            jobs = await RemoshiftConnector().collect(None, Settings(max_per_source=20))
        assert len(jobs) == 1
        assert jobs[0].url == "https://remoshift.com/jobs/11"
        assert jobs[0].japan_ok == "unknown"
    asyncio.run(run())


def test_jobicy_broad_single_fetch_without_tag_filter():
    payload = {"jobs": [
        {"id": 33, "jobTitle": "AI Operations Contractor", "url": "https://jobicy.com/jobs/33",
         "jobGeo": "Anywhere", "companyName": "Example Inc"}
    ]}
    async def run():
        with patch("app.core.request_json", new=AsyncMock(return_value=payload)) as mock_get:
            jobs = await JobicyConnector().collect(None, Settings(max_per_source=5))
            assert len(jobs) == 1
            assert mock_get.await_count == 1
            assert "tag" not in mock_get.call_args.kwargs["params"]
    asyncio.run(run())
