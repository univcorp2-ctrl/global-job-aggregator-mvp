"""The auto-apply queue is real and persistent; it must never fabricate submissions."""
import sqlite3
import pytest
from app.auto_application_queue import (
    prepare,mark_submitted,_key,_state_for,SCHEMA
)
from app.core import NormalizedJob,connect,init_db,upsert_job


def test_ai_first_queue_is_persistent_and_deduplicated(tmp_path):
    db=tmp_path/"jobs.db"
    dest=tmp_path/"queue.db"
    init_db(db)
    with connect(db) as c:
        upsert_job(c,NormalizedJob(
            source="himalayas",external_id="1",title="Python CSV automation",
            url="https://himalayas.app/jobs/1",
            description="Fixed-price one-off CSV report and Python script deliverable",
            contract_type="contractor",company="A"
        ))
        upsert_job(c,NormalizedJob(
            source="jobicy",external_id="2",title="Freelance Writer",
            url="https://jobicy.com/jobs/2",description="Weekly content writing",
            contract_type="contractor"
        ))
    a=prepare(db,dest)
    b=prepare(db,dest)
    assert a["new_prequalified"]==1
    assert b["new_prequalified"]==0
    assert b["status_counts"]["qualification_pending"]==1
    assert b["external_submissions"]==0
    with sqlite3.connect(dest) as q:
        row=q.execute("SELECT status,draft,provider_receipt FROM application_intents").fetchone()
        assert row[0]=="qualification_pending" and "Python" in row[1] and row[2] is None
        assert q.execute("SELECT COUNT(*) FROM application_events").fetchone()[0]==1


def test_cannot_fake_submissions_or_cross_provider_gate():
    con=sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    h=_key("upwork","https://upwork.com/jobs/1")
    with pytest.raises(PermissionError):
        mark_submitted(con,h,"fake-confirmation",official_adapter_verified=False)
    with pytest.raises(PermissionError):
        mark_submitted(con,h,"verified-but-unexpected",official_adapter_verified=True)
    assert con.execute("SELECT COUNT(*) FROM application_intents WHERE status='submitted'").fetchone()[0]==0


def test_reject_malicious_and_unqualified_jobs():
    assert _state_for({"source":"jobicy","url":"javascript:alert(1)","title":"CSV report",
         "description":"Python automation"}) is None
    assert _state_for({"source":"jobicy","url":"https://jobicy.com/1","title":"Full Time Manager",
         "description":"Annual salary job"}) is None
    assert _state_for({"source":"jobicy","url":"https://jobicy.com/1","title":"Python export",
         "description":"One-off CSV report deliverable"})=="qualification_pending"
