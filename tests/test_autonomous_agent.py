"""No-contact and no-payment regression tests for autonomous opportunity scouting."""
import asyncio
import httpx
from app.autonomous_agent import (catalog_mcp, catalog_apify,
                                   evaluate_database, score_candidate, _feedback_multiplier)
from app.core import NormalizedJob, connect, enrich_job, init_db, upsert_job

def test_registry_and_store_are_read_only():
    calls = []
    def handler(r):
        calls.append(r.method)
        if "registry.modelcontextprotocol.io" in str(r.url):
            return httpx.Response(200, json={"servers": [
                {"server": {"name": "example/mcp", "title": "Example MCP", "description": "Test"}}]})
        return httpx.Response(200, json={"data":{"items":[
            {"id":"actor1","title":"Example data product","url":"https://apify.com/example"}]}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await catalog_mcp(c, terms=("marketplace",)), await catalog_apify(c, terms=("data",))
    (mcp, mstat), (actors, astat) = asyncio.run(run())
    assert mstat["state"] == astat["state"] == "read_only_success"
    assert len(mcp) == len(actors) == 1
    assert mcp[0]["automatically_installed"] is False
    assert actors[0]["verified_customer_purchase"] is False
    assert calls == ["GET", "GET"]

def test_fail_closed_if_registry_down():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(503))) as c:
            return await catalog_mcp(c, terms=("market",))
    entries, state = asyncio.run(run())
    assert entries == [] and state["state"] == "unavailable"

def test_no_invented_financial_outcomes_or_unsigned_contracts():
    row={"source":"jobicy","external_id":"001","title":"Python automation freelance contractor",
         "contract_type":"contractor","ai_relevance":80,"fit_score":90,
         "url":"https://jobs.example.com/001","proposal_draft":"NOT SENT"}
    r=score_candidate(row)
    assert r["opportunity_type"] == "possible_paid_project_unverified"
    assert r["expected_net_profit"] is None
    assert r["is_confirmed_contract"] is False
    assert r["draft_only"] == "NOT SENT"
    r2=score_candidate({**row,"title":"Full-time employee salary role"})
    assert r2["opportunity_type"] == "employment_not_subcontractable_without_new_contract"
    assert score_candidate({**row,"url":"javascript:alert(1)"})["url"] is None

def test_bounded_feedback_based_only_on_verified_history():
    r={"source":"test"}
    assert _feedback_multiplier(r, {"test":{"submitted":1,"won":1}}) == 1.0
    assert _feedback_multiplier(r, {"test":{"submitted":1,"won":2}}) == 1.0
    assert .85 <= _feedback_multiplier(r, {"test":{"submitted":40,"won":10}}) <= 1.15

def test_queue_uses_existing_deduplicated_db(tmp_path):
    db=tmp_path/"jobs.db"
    init_db(db)
    row=enrich_job(NormalizedJob(source="remotive", external_id="1",
          title="AI automation freelance contractor", contract_type="contractor",
          url="https://example.org/gig",description="OpenAI API consulting project"))
    with connect(db) as conn:
        upsert_job(conn,row)
        upsert_job(conn,row)
    r=evaluate_database(db,{})
    assert r["source_counts"]["remotive"] == 1
    assert len(r["shortlist"]) == 1
    assert r["queued_for_automatic_submission"] == 0
