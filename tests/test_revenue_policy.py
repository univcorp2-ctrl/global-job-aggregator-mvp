"""No worker scouting before a funded authorized award; public job feed privacy."""
import json
from datetime import datetime, timezone

from app.revenue_policy import subcontract_gate, triage
from app.core import NormalizedJob, connect, init_db, upsert_job
from scripts.global_work_mesh import publishable_jobs, export


def test_never_scout_workers_without_an_award():
    assert subcontract_gate(None)["may_search_workers"] is False
    base = {"state":"active","provider_contract_id":"contract-123",
            "subcontract_consent":True,"provider_policy_allows":True,
            "ai_delivery_failed":True,"funded":True}
    for key in list(base):
        candidate=dict(base)
        candidate[key]=False if isinstance(base[key],bool) else ""
        assert subcontract_gate(candidate)["may_search_workers"] is False
    assert subcontract_gate(base)["may_search_workers"] is True
    assert subcontract_gate(base)["may_commit_money"] is False


def test_not_all_freelance_jobs_are_autonomous_projects():
    bad=[
        {"title":"Freelance Writer","contract_type":"contract"},
        {"title":"Inside Sales Contractor","description":"full-time calling and sales","contract_type":"contractor"},
        {"title":"Manager Europe Remote in Brazil","description":"permanent role, annual salary"},
        {"title":"Voice-over for science video","description":"record your voice live","contract_type":"fixed-price"},
    ]
    for row in bad:
        assert triage(row)["ai_only_candidate"] is False
    yes=triage({"title":"Python API integration","contract_type":"fixed-price",
                "description":"One-off project: deliverable CSV spreadsheet and Python script"})
    assert yes["ai_only_candidate"] is True
    assert yes["confirmed_ai_deliverable"] is False


def test_world_board_only_licensed_links_and_no_private_metadata(tmp_path):
    db=tmp_path/"jobs.db"
    init_db(db)
    entries=[
        NormalizedJob(source="jobicy",external_id="job1",title="AI data extraction",
                      company="Example",url="https://jobicy.com/jobs/job1",
                      description="CSV report deliverable",contract_type="contractor"),
        NormalizedJob(source="himalayas",external_id="job2",title="CSV report",
                      company="Other",url="https://himalayas.app/companies/foo/jobs/bar",
                      description="One-off report",raw={"applicationLink":"https://himalayas.app/companies/foo/jobs/bar"}),
        NormalizedJob(source="remotive",external_id="job3",title="Private source",
                      url="https://remotive.com/remote-jobs/3"),
        NormalizedJob(source="jobicy",external_id="job4",title="Malicious link",
                      url="javascript:alert(1)")
    ]
    with connect(db) as conn:
        for item in entries: upsert_job(conn,item)
    jobs=publishable_jobs(db)
    assert {x["source"] for x in jobs}=={"Jobicy","Himalayas"}
    assert len(jobs)==2
    assert all(not any(k in x for k in ("raw_json","external_id","worker","email")) for x in jobs)
    assert jobs[0]["url"].startswith("https://")
    output=tmp_path/"site"
    payload=export(db,output)
    assert payload["listing_count"]==2
    assert set(f.name for f in output.iterdir())=={"index.html","style.css","app.js","_headers","jobs.json"}
    assert "Private source" not in (output/"jobs.json").read_text("utf8")
