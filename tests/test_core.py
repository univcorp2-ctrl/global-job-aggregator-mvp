import asyncio

import httpx
import respx

from app.core import HimalayasConnector, NormalizedJob, Settings, connect, enrich_job, get_job, init_db, list_jobs, upsert_job


def test_enrich_job_scores_ai_automation_role() -> None:
    job = NormalizedJob(source="test", external_id="1", title="AI Agent Developer for RAG workflow automation", company="ExampleCo", compensation="$120/hr", description="Build OpenAI API integrations with LangChain, vector database search, and n8n.")
    enrich_job(job)
    assert job.ai_relevance >= 40
    assert job.application_priority in {"A", "B"}
    assert "OpenAI API" in job.required_skills
    assert job.expected_monthly_income is not None
    assert "AI" in job.proposal_draft


def test_upsert_and_list_jobs(tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    init_db(db_path)
    job = enrich_job(NormalizedJob(source="unit", external_id="abc", title="RAG Engineer", company="Demo", url="https://example.com/job", description="OpenAI API and vector database project"))
    with connect(db_path) as conn:
        assert upsert_job(conn, job) is True
        rows = list_jobs(conn, q="rag")
        assert len(rows) == 1
        assert rows[0]["title"] == "RAG Engineer"
        assert rows[0]["required_skills"]
        detail = get_job(conn, rows[0]["id"])
        assert detail is not None
        assert detail["company"] == "Demo"


def test_himalayas_connector_normalizes_jobs() -> None:
    settings = Settings(keywords=["python"], max_per_source=5, request_delay_seconds=0)

    async def run():
        async with httpx.AsyncClient() as client:
            return await HimalayasConnector().collect(client, settings)

    with respx.mock:
        respx.get("https://himalayas.app/jobs/api/search").mock(return_value=httpx.Response(200, json={"jobs": [{"guid": "job-1", "title": "Senior Python AI Engineer", "companyName": "RemoteCo", "applicationLink": "https://example.com/apply", "employmentType": "Contract", "minSalary": 100000, "maxSalary": 150000, "currency": "USD", "locationRestrictions": [], "description": "<p>Build RAG with OpenAI API</p>", "pubDate": "2026-01-01T00:00:00Z"}]}))
        jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source == "himalayas"
    assert jobs[0].remote == "remote"
    assert jobs[0].japan_ok == "yes"
    assert jobs[0].compensation == "USD 100,000 - 150,000"
