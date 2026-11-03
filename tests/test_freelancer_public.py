"""Freelancer.com official public projects API: stable read-only integration."""
import asyncio
import httpx
import pytest

@pytest.fixture(autouse=True)
def approved_test_api_access(monkeypatch):
    monkeypatch.setenv('FLN_API_WRITTEN_PERMISSION','true')
from app.core import (FreelancerPublicConnector, Settings, connect,
                      default_connectors, enrich_job, init_db, upsert_job)

def test_freelancer_get_only_and_ignore_unrelated_results(tmp_path):
    methods=[]
    def handler(req):
        methods.append(req.method)
        return httpx.Response(200, json={"status":"success","result":{"projects":[
          {"id":4079,"status":"active","title":"Excel invoice data extraction",
           "type":"fixed","seo_url":"excel/Invoice-Extraction",
           "currency":{"code":"USD"},"budget":{"minimum":50,"maximum":100},
           "bid_stats":{"bid_count":9},"jobs":[{"name":"Excel"}],
           "description":"Audit 100 invoices and deliver editable spreadsheet",
           "time_submitted":1793180000},
          {"id":4080,"status":"active","title":"Spanish voice acting",
           "seo_url":"audio/Spanish-Voice","jobs":[{"name":"Audio"}],
           "budget":{"minimum":20,"maximum":40}},
          {"id":4081,"status":"closed","title":"Python automation",
           "seo_url":"python/closed","jobs":[{"name":"Python"}]}
        ]}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await FreelancerPublicConnector().collect(c,Settings(max_per_source=10))
    found=asyncio.run(run())
    assert len(found)==1
    row=found[0]
    assert row.source=="freelancer_public"
    assert row.url=="https://www.freelancer.com/projects/excel/Invoice-Extraction"
    assert row.compensation=="USD 50 - 100"
    assert row.raw["bid_count"]==9
    assert "freelance project" in row.contract_type
    assert methods==["GET","GET","GET"]
    path=tmp_path/"jobs.db"
    init_db(path)
    with connect(path) as db:
        assert upsert_job(db,enrich_job(row)) is True

def test_freelancer_no_description_and_budget_and_default_wired():
    assert "freelancer_public" in [c.name for c in default_connectors()]
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200,json={"status":"success","result":{"projects":[
                {"id":70,"status":"active","title":"Python automation",
                 "seo_url":"python/Python-Automation","type":"hourly",
                 "currency":{"code":"USD"},"budget":{}}
            ]}})
        )) as c:
            return await FreelancerPublicConnector().collect(c,Settings(max_per_source=5))
    rows=asyncio.run(run())
    assert len(rows)==1
    assert rows[0].description==""
    assert rows[0].compensation is None
    assert rows[0].contract_type=="hourly freelance project"


def test_actual_bid_count_reduces_priority_but_not_below_zero():
    from app.autonomous_agent import score_candidate
    source={"source":"freelancer_public","title":"Python freelance automation",
            "contract_type":"fixed freelance project",
            "ai_relevance":90,"fit_score":80,"url":"https://www.freelancer.com/projects/example",
            "raw":{"bid_count":0}}
    quiet=score_candidate(source)
    crowded=score_candidate({**source,"raw":{"bid_count":120}})
    assert quiet["score"] > crowded["score"]
    assert crowded["score"] >= 0
    assert quiet["is_confirmed_contract"] is False
