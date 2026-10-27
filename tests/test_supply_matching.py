"""Offline privacy, matching and authorization tests; no network required."""
from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main as app_module
from app.supply_connectors import freelancer_search, API
from app.workers import (
    connect_workers, match_workers, prepare_contact, provider_capabilities,
    register_worker, search_workers,
)


def _add_opted_in_worker(db):
    return register_worker(
        db, platform="opt_in", external_id="test-001",
        display_label="Consenting test contributor",
        skills=["Python", "OpenAI API", "n8n"], location="Japan",
        remote_ok=True, hourly_rate=80, currency="USD",
    )


def test_no_worker_profiles_until_opt_in():
    with TemporaryDirectory() as tmp:
        with connect_workers(Path(tmp) / "workers.db") as db:
            assert search_workers(db) == []
            with pytest.raises(ValueError, match="consent"):
                register_worker(db,platform="opt_in",external_id="test",
                                display_label="Anonymous",skills=["python"],
                                consent_basis="unknown")


def test_worker_match_and_platform_scoped_draft_do_not_send():
    with TemporaryDirectory() as tmp:
        with connect_workers(Path(tmp) / "workers.db") as db:
            uid=_add_opted_in_worker(db)
            jobs={"id":9,"title":"Python / OpenAI API integration",
                  "description":"Automate n8n workflows","required_skills":["Python","OpenAI API"]}
            workers=search_workers(db,skill="python")
            assert len(workers)==1
            assert workers[0]["skills"]==["python","openai api","n8n"]
            ranked=match_workers(db,jobs)
            assert ranked and ranked[0]["worker_id"]==uid
            assert ranked[0]["status"]=="candidate_only_subcontract_permission_unverified"
            draft=prepare_contact(db,job=jobs,worker_id=uid)
            assert draft["state"]=="prepared_not_sent"
            assert draft["send_enabled"] is False
            assert draft["requires_verified_subcontract_rights"] is True
            assert db.execute("SELECT COUNT(*) FROM contact_drafts").fetchone()[0]==1


def test_off_platform_urls_and_unverified_source_import_blocked():
    with TemporaryDirectory() as tmp:
        with connect_workers(Path(tmp) / "workers.db") as db:
            with pytest.raises(ValueError,match="own platform"):
                register_worker(db,platform="contra",external_id="profile",display_label="x",
                                skills=["python"],profile_url="https://example.com/person")
            with pytest.raises(ValueError,match="official API"):
                register_worker(db,platform="freelancer",external_id="profile",display_label="x",
                                skills=["python"],consent_basis="platform_authorized",
                                profile_origin="scraped")
            with pytest.raises(ValueError,match="HTTPS"):
                register_worker(db,platform="opt_in",external_id="profile",display_label="x",
                                skills=["python"],profile_url="http://example.com/me")


def test_providers_do_not_claim_connections():
    p=provider_capabilities()
    assert p["contra"]["connected"] is False
    assert p["freelancer"]["connected"] is False
    assert p["coconala"]["contact"]=="on_platform_only"


def test_freelancer_without_oauth_is_fail_closed(monkeypatch):
    monkeypatch.delenv("FREELANCER_OAUTH_TOKEN",raising=False)
    data=asyncio.run(freelancer_search(query="python"))
    assert data["connected"] is False
    assert data["profiles"]==[]
    assert data["blocked_reason"]=="official_oauth_token_required"


def test_freelancer_preview_filters_direct_contact_details():
    payload={"result":{"users":[{"username":"skills_worker",
        "display_name":"Test Contributor",
        "skills":["Python","Data Analysis"],
        "email":"private@example.com","phone":"0000000000"},
        {"username":"invalid username"}]}}
    def respond(req):
        assert str(req.url).startswith(API)
        assert req.headers["Freelancer-OAuth-V1"]=="placeholder"
        return httpx.Response(200,json=payload)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await freelancer_search(query="python",token="placeholder",client=client)
    data=asyncio.run(run())
    assert data["connected"] is True
    assert len(data["profiles"])==1
    assert "email" not in data["profiles"][0]
    assert "phone" not in data["profiles"][0]
    assert data["may_persist"] is False


def test_public_worker_routes_deny_access_without_secret(monkeypatch):
    monkeypatch.delenv("WORKER_DB_TOKEN",raising=False)
    with TestClient(app_module.app) as cli:
        assert cli.get("/api/workers").status_code==401
        assert cli.get("/api/supply/providers").status_code==401
        assert cli.get("/api/matches/1").status_code==401
        assert cli.get("/api/workers/discover/freelancer").status_code==401
        assert cli.post("/api/workers",json={}).status_code in (401,422)
        assert cli.get("/workers").status_code==200  # HTML shell only, no worker data


def test_api_worker_opt_in_and_private_lookup(monkeypatch,tmp_path):
    monkeypatch.setenv("WORKER_DB_TOKEN","test-only-secret")
    monkeypatch.setattr(app_module,"WORKERS_DB_PATH",tmp_path/"worker-registry.db")
    with TestClient(app_module.app) as cli:
        headers={"x-worker-token":"test-only-secret"}
        payload={"platform":"opt_in","external_id":"demo","display_label":"Demo Worker",
                 "skills":["Python","Automation"],"worker_opted_in":True}
        denied=cli.post("/api/workers",json={**payload,"worker_opted_in":False},headers=headers)
        assert denied.status_code==422
        created=cli.post("/api/workers",json=payload,headers=headers)
        assert created.status_code==200
        assert created.json()["contact_authorized"] is False
        assert cli.get("/api/workers",headers={"x-worker-token":"bad"}).status_code==401
        data=cli.get("/api/workers?skill=python",headers=headers)
        assert data.status_code==200
        assert data.json()["count"]==1


def test_end_to_end_job_from_one_source_worker_from_another(monkeypatch,tmp_path):
    from app.core import Settings, NormalizedJob, init_db, connect, upsert_job, list_jobs
    secret = "local-e2e-only"
    monkeypatch.setenv("WORKER_DB_TOKEN", secret)
    job_db = tmp_path / "jobs.db"
    worker_db = tmp_path / "private-workers.db"
    monkeypatch.setattr(app_module,"settings",Settings(db_path=job_db))
    monkeypatch.setattr(app_module,"WORKERS_DB_PATH",worker_db)
    init_db(job_db)
    conn = connect(job_db)
    try:
        upsert_job(conn,NormalizedJob(
            source="remotive",external_id="project-2026",
            title="Python API workflow automation",
            url="https://remotive.com/remote-jobs/software-development/example",
            description="Integrate OpenAI API and n8n workflows",
        ))
        job_id = list_jobs(conn,limit=1)[0]["id"]
    finally:
        conn.close()
    headers = {"x-worker-token":secret}
    with TestClient(app_module.app) as cli:
        created = cli.post("/api/workers",json={
            "platform":"opt_in","external_id":"consenting-remote-01",
            "display_label":"Opt-in contractor",
            "skills":["python","openai api","n8n"],"remote_ok":True,
            "worker_opted_in":True,
        },headers=headers)
        assert created.status_code==200
        worker_id=created.json()["id"]
        result=cli.get(f"/api/matches/{job_id}",headers=headers)
        assert result.status_code==200
        matches=result.json()["matches"]
        assert matches and matches[0]["worker_id"]==worker_id
        assert "unverified" in matches[0]["status"]
        inquiry=cli.post("/api/workers/contact-draft",
            json={"job_id":job_id,"worker_id":worker_id},headers=headers)
        assert inquiry.status_code==200
        assert inquiry.json()["state"]=="prepared_not_sent"
        assert inquiry.json()["send_enabled"] is False
        assert inquiry.json()["needs_platform_permission"] is True
        assert cli.post("/api/workers/contact-draft",
            json={"job_id":job_id,"worker_id":"missing"},headers=headers).status_code==404
