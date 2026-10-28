"""The 100-application target counts ONLY native confirmed submissions."""
import asyncio
import json
from datetime import datetime, timezone

import httpx

from scripts.application_campaign import collect, normalize
from scripts.revenue_dashboard import build_public_payload


def demo(id=1234, title="Excel CSV automation", bids=5):
    return {
        "id":id, "status":"active","title":title,
        "seo_url":"excel/CSV-Automation","jobs":[{"name":"Excel"},{"name":"Python"}],
        "description":"Provide an Excel and CSV data cleaning report as a fixed-price project",
        "type":"fixed","budget":{"minimum":50,"maximum":250},
        "currency":{"code":"USD"},"bid_stats":{"bid_count":bids},
        "time_submitted":1793180000,
    }


def test_curation_rejects_irrelevant_and_high_competition():
    assert normalize(demo()) is not None
    assert normalize(demo(title="Arabic Translation")) is None
    assert normalize(demo(bids=200)) is None
    assert normalize({**demo(),"status":"closed"}) is None
    assert normalize({**demo(),"seo_url":"https://evil.example.com"}) is None
    assert normalize({**demo(),"budget":{"minimum":0}}) is None
    assert normalize({**demo(),"title":"Boost Genuine Amazon Reviews"}) is None


def test_public_get_only_and_deduplicates_project():
    calls=[]
    def respond(req):
        calls.append(req.method)
        return httpx.Response(200,json={"status":"success","result":{"projects":[
            demo(),demo(),demo(1235,title="Python CSV automation",bids=7)
        ]}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
            return await collect(c,pages=1,page_size=25,target=100)
    records,info=asyncio.run(run())
    assert len(records)==2
    assert all(x.source=="freelancer_public" for x in records)
    assert info["raw_rows_scanned"]==len(calls)*3
    assert all(x=="GET" for x in calls)


def test_dashboard_cannot_confuse_proposals_and_submissions(tmp_path):
    now=datetime.now(timezone.utc).isoformat()
    (tmp_path/"upwork-application-verification.json").write_text(
        json.dumps({"provider":"upwork_official_mcp","verified_at":now,
                    "submitted":0,"pending":0,"invitations":0,
                    "target_status":"not_submitted","connects_balance":12,
                    "target_connects_cost":10}),encoding="utf-8")
    (tmp_path/"application-campaign-status.json").write_text(
        json.dumps({"run_at":now,"goal_verified_applications":100,
                    "marketplace_leads_scanned":557,
                    "queue_total_by_status":{"qualification_pending":41,
                                              "draft_ready":30,"rejected":7},
                    "api_errors":0,
                    "private_job_id":"DO_NOT_PUBLISH",
                    "token":"MY_SECRET"}),encoding="utf-8")
    public=build_public_payload(tmp_path)
    goal=public["application_goal"]
    assert goal["target"]==100
    assert goal["verified_submitted"]==0
    assert goal["candidate_queue"]==71
    assert goal["marketplace_rows_screened"]==557
    assert goal["provider_bids_sent"]==0
    assert public["metrics"]["applications"]==0
    content=json.dumps(public)
    assert "DO_NOT_PUBLISH" not in content
    assert "MY_SECRET" not in content
