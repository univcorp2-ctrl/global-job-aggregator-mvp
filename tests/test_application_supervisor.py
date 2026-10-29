"""Application dispatch cannot be forged and never sends without provider permissions."""
import json
import sqlite3
from datetime import datetime, timezone

from scripts.application_supervisor import gates, qualify, run
from app.core import NormalizedJob, connect, init_db, upsert_job
from app.auto_application_queue import prepare


def candidate(title="Python CSV automation",external_id="40790011",
              compensation="USD 80 - 150", raw=None):
    return NormalizedJob(
        source="freelancer_public",external_id=external_id,title=title,
        url=f"https://www.freelancer.com/projects/python/{external_id}",
        description=("Build a Python automated CSV workbook with validation and "
                     "error logging, support multiple input formats and include "
                     "clear instructions to operate and verify the processed files."),
        compensation=compensation,contract_type="fixed freelance project",
        published_at=datetime.now(timezone.utc).isoformat(),
        raw=raw or {"project_status":"active","bid_count":4,
                    "budget_currency":"USD","budget_type":"fixed"}
    )


def setup(root):
    db=root/"jobs.db"
    init_db(db)
    with connect(db) as conn:
        upsert_job(conn,candidate())
        upsert_job(conn,candidate(title="English-Portuguese Formal Translation",
                                  external_id="40790012"))
    prepare(db,root/"application-intents.db",limit=30)


def test_qualify_avoids_unsuited_language_and_hourly():
    base={"source":"freelancer_public","external_id":"40790011",
          "title":"Python CSV automation",
          "description":candidate().description,
          "url":candidate().url,
          "compensation":"USD 80 - 150",
          "contract_type":"fixed freelance project",
          "published_at":datetime.now(timezone.utc).isoformat(),
          "raw_json":json.dumps({"project_status":"active","bid_count":5,
                                 "budget_currency":"USD"})}
    assert qualify(base)["amount"]==88
    assert qualify({**base,"title":"English-Portuguese Formal Translation"}) is None
    assert qualify({**base,"contract_type":"hourly freelance project"}) is None
    assert qualify({**base,"raw_json":json.dumps({"project_status":"closed"})}) is None
    assert qualify({**base,"compensation":"USD 0 - 50"}) is None


def test_blocks_without_platform_permission_and_reports_it(tmp_path):
    setup(tmp_path)
    calls=[]
    env={"FLN_OAUTH_TOKEN":"fixture_no_remote_calls",
         "FLN_AUTOBID_ENABLED":"true"}
    status=run(tmp_path,env=env,send=lambda item:calls.append(item) or "123")
    assert calls==[]
    assert not gates(env)["authorized"]
    assert status["native_submitted_total"]==0
    assert status["high_fit_eligible"]==1
    assert status["providers"][1]["state"]=="blocked_permission"
    assert status["dispatch_states"].get("blocked")==1
    assert "fixture_no_remote_calls" not in (tmp_path/"application-supervisor-status.json").read_text()


def test_verified_receipt_counts_once_even_across_repeated_ticks(tmp_path):
    setup(tmp_path)
    fake_env={"FLN_OAUTH_TOKEN":"fixture","FLN_API_WRITTEN_PERMISSION":"true",
              "FLN_AUTOBID_ENABLED":"true","FLN_PROFILE_VERIFIED":"true"}
    sent=[]
    def sdk_stub(proposal):
        sent.append(proposal)
        return "501234567"
    a=run(tmp_path,env=fake_env,send=sdk_stub)
    b=run(tmp_path,env=fake_env,send=sdk_stub)
    assert a["native_submitted_this_tick"]==1
    assert a["native_submitted_total"]==1
    assert b["native_submitted_this_tick"]==0
    assert b["native_submitted_total"]==1
    assert len(sent)==1
    with sqlite3.connect(tmp_path/"application-dispatch.db") as conn:
        assert conn.execute("SELECT receipt FROM dispatch_attempts WHERE state='submitted_verified'").fetchone()[0]=="501234567"


def test_ambiguous_send_never_retries_automatically(tmp_path):
    setup(tmp_path)
    env={"FLN_OAUTH_TOKEN":"fixture","FLN_API_WRITTEN_PERMISSION":"true",
         "FLN_AUTOBID_ENABLED":"true","FLN_PROFILE_VERIFIED":"true"}
    n=[0]
    def fail(_):
        n[0]+=1
        raise RuntimeError("timeout after provider maybe accepted")
    first=run(tmp_path,env=env,send=fail)
    again=run(tmp_path,env=env,send=fail)
    assert n[0]==1
    assert first["unknown_outcome"]==1
    assert again["unknown_outcome"]==1
    assert again["native_submitted_total"]==0



def test_blocked_rows_resume_once_when_provider_approved(tmp_path):
    setup(tmp_path)
    blocked=run(tmp_path,env={},send=lambda x:"9999")
    assert blocked["native_submitted_total"]==0
    approved={"FLN_OAUTH_TOKEN":"fixture", "FLN_API_WRITTEN_PERMISSION":"true",
              "FLN_AUTOBID_ENABLED":"true", "FLN_PROFILE_VERIFIED":"true"}
    calls=[]
    a=run(tmp_path,env=approved,send=lambda job:calls.append(job) or "501234567")
    b=run(tmp_path,env=approved,send=lambda job:calls.append(job) or "501234567")
    assert a["native_submitted_total"]==1
    assert b["native_submitted_total"]==1
    assert len(calls)==1


def test_deny_public_freelancer_api_without_permission():
    from unittest.mock import AsyncMock, patch
    import asyncio
    import pytest
    from app.core import FreelancerPublicConnector, Settings
    async def execute():
        with patch("app.core.request_json",new=AsyncMock()) as mocked:
            with pytest.raises(PermissionError):
                await FreelancerPublicConnector().collect(None,Settings(max_per_source=5))
            mocked.assert_not_awaited()
    with patch.dict("os.environ",{"FLN_API_WRITTEN_PERMISSION":""}):
        asyncio.run(execute())


def test_official_campaign_stops_network_without_permission(tmp_path):
    import asyncio
    from unittest.mock import patch
    from scripts.application_campaign import run as run_campaign
    (tmp_path/"application-campaign-status.json").write_text(
        json.dumps({"marketplace_leads_scanned":557,"run_at":"2026-10-28T13:33:02Z"}),
        encoding="utf-8")
    with patch.dict("os.environ",{"FLN_API_WRITTEN_PERMISSION":""}):
        out=asyncio.run(run_campaign(tmp_path))
    assert out["collection_state"]=="paused_pending_provider_written_permission"
    assert out["marketplace_leads_scanned"]==557
    assert out["provider_bids_sent"]==0
