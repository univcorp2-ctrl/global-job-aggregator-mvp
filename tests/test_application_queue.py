"""Private AI-first application queue; no unsolicited proposals or subcontracts."""
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.application_queue import (connect_queue,add_candidate,list_queue,
    plan_submission,classify_delivery)


def sample(**override):
    d=dict(platform="upwork",external_job_id="999",title="Excel formula task",
        job_url="https://www.upwork.com/jobs/~02999",budget_amount=50.0,
        application_credits=10,expected_ai_tasks=["generate xlsx","test formulas"],
        specialist_tasks=[],draft_text="Please consider my application")
    d.update(override)
    return d


def test_queue_idempotence_and_never_marks_sent():
    with TemporaryDirectory() as d:
        with connect_queue(Path(d)/"applications.db") as db:
            a=add_candidate(db,**sample())
            b=add_candidate(db,**sample())
            assert a["id"]==b["id"]
            assert len(list_queue(db))==1
            row=list_queue(db)[0]
            assert row["status"]=="draft_ready"
            assert row["is_submitted"] is False
            r=plan_submission(db,a["id"],remaining_credits=12)
            assert r["status"]=="awaiting_platform_preview_and_specific_approval"
            assert r["needs_attachments_choice"] is True
            assert r["human_confirmation_required_for_each_preview"] is True
            assert r["sent"] is False
            assert r["submitted"] is False


def test_queue_blocks_spending_beyond_connects():
    with TemporaryDirectory() as d:
        with connect_queue(Path(d)/"app.db") as db:
            x=add_candidate(db,**sample(application_credits=18))
            decision=plan_submission(db,x["id"],remaining_credits=12)
            assert decision["status"]=="blocked"
            assert "insufficient_platform_credits" in decision["reasons"]
            assert decision["platform_action"]=="none"


def test_queue_blocks_specialist_without_contract_permission():
    with TemporaryDirectory() as d:
        with connect_queue(Path(d)/"app.db") as db:
            x=add_candidate(db,**sample(specialist_tasks=["licensed accounting approval"]))
            decision=plan_submission(db,x["id"],remaining_credits=12)
            assert "external_specialist_work_requires_client_permission" in decision["reasons"]
            assert decision["sent"] is False


def test_queue_never_accepts_other_platform_host_or_no_ai_work():
    with TemporaryDirectory() as d:
        with connect_queue(Path(d)/"app.db") as db:
            with pytest.raises(ValueError,match="host"):
                add_candidate(db,**sample(job_url="https://www.fake.example/job"))
            with pytest.raises(ValueError,match="AI-first"):
                add_candidate(db,**sample(expected_ai_tasks=[]))


def test_subcontract_routing_fails_closed():
    no=classify_delivery(specialist_tasks=["designer"],subcontract_allowed=False)
    assert no["routing"]=="hold_specialist_tasks"
    assert no["may_outsource"] is False
    partial=classify_delivery(specialist_tasks=["designer"],
       subcontract_allowed=True,has_specialist_consent=False)
    assert partial["may_outsource"] is False
    ready=classify_delivery(specialist_tasks=["designer"],
       subcontract_allowed=True,has_specialist_consent=True,
       has_customer_data_permission=True)
    assert ready["may_outsource"] is True
    assert ready["send_enabled"] is False
    ai=classify_delivery(specialist_tasks=[],subcontract_allowed=False)
    assert ai["routing"]=="ai_first"
    assert ai["may_outsource"] is False


def test_intake_routes_require_owner_token(monkeypatch):
    monkeypatch.delenv("WORKER_DB_TOKEN",raising=False)
    with TestClient(main.app) as cli:
        assert cli.get("/applications").status_code==200
        assert cli.get("/api/applications/queue").status_code==401
        assert cli.post("/api/applications/queue",json=sample()).status_code==401
        assert cli.post("/api/applications/delivery-route",json={}).status_code==401


def test_one_candidate_api_flow_no_send(monkeypatch,tmp_path):
    monkeypatch.setenv("WORKER_DB_TOKEN","test-secret-application")
    monkeypatch.setattr(main,"APPLICATIONS_DB_PATH",tmp_path/"applications.db")
    headers={"x-worker-token":"test-secret-application"}
    with TestClient(main.app) as cli:
        result=cli.post("/api/applications/queue",json=sample(),headers=headers)
        assert result.status_code==200
        queue=cli.get("/api/applications/queue",headers=headers)
        assert queue.status_code==200
        assert queue.json()["count"]==1
        assert queue.json()["sent_total"]==0
        uid=result.json()["id"]
        decision=cli.get(f"/api/applications/{uid}/readiness?remaining_credits=12",headers=headers)
        assert decision.status_code==200
        assert decision.json()["status"]=="awaiting_platform_preview_and_specific_approval"
        assert decision.json()["sent"] is False
        route=cli.post("/api/applications/delivery-route",
                       json={"specialist_tasks":["design"],"subcontract_allowed":False},headers=headers)
        assert route.json()["may_outsource"] is False


def test_ai_first_jobs_rejected_when_client_explicitly_prohibits_ai():
    from app.application_queue import assess_job_constraints
    original = ("The final wording must be written by you, without generative AI. "
                "Documentation must reflect actual workbook behavior.")
    outcome=assess_job_constraints(original)
    assert outcome["screening_state"]=="reject_ai_first"
    assert outcome["flags"]["explicit_no_ai"] is True
    assert outcome["auto_send_enabled"] is False


def test_subcontracting_never_assumed_from_silence():
    from app.application_queue import assess_job_constraints
    outcome=assess_job_constraints("Make a dynamic Excel round robin schedule for 8 to 48 players.")
    assert outcome["screening_state"]=="manual_scope_and_platform_review"
    assert outcome["subcontract_rights"]=="not_established"
    assert outcome["ai_use_rights"]=="not_established"


def test_explicit_subcontract_ban_holds_outsourcing():
    from app.application_queue import assess_job_constraints
    outcome=assess_job_constraints("No agencies or third-party contractors. You must personally deliver.")
    assert outcome["flags"]["explicit_no_subcontract"] is True
    assert outcome["subcontract_rights"]=="prohibited"
    assert outcome["auto_send_enabled"] is False
