"""Visible progress is provably read-only and does not count drafts as bids."""
import json
import sqlite3
from datetime import datetime, timezone

from scripts.application_monitor import run
from scripts.revenue_dashboard import build_public_payload


def test_read_only_monitor_does_not_invent_submissions(tmp_path):
    q=sqlite3.connect(tmp_path/"application-intents.db")
    q.executescript("""
    CREATE TABLE application_intents(status TEXT);
    INSERT INTO application_intents VALUES('qualification_pending');
    INSERT INTO application_intents VALUES('draft_ready');
    INSERT INTO application_intents VALUES('rejected');
    """)
    q.close()
    d=sqlite3.connect(tmp_path/"application-dispatch.db")
    d.executescript("""
    CREATE TABLE dispatch_attempts(state TEXT);
    INSERT INTO dispatch_attempts VALUES('blocked');
    INSERT INTO dispatch_attempts VALUES('blocked');
    """)
    d.close()
    (tmp_path/"upwork-application-history.json").write_text(
        json.dumps({"schema":1,"verification_source":"Upwork official MCP",
        "entries":[{"status":"submitted","provider_status_label":"Submitted"}]}),
        encoding="utf-8")
    status=run(tmp_path)
    assert status["candidate_queue"]==2
    assert status["drafts_created"]==2
    assert status["official_upwork_submitted"]==1
    assert status["native_submitted_total"]==0
    assert status["execution_mode"]=="read_only_review_and_audit"
    web=build_public_payload(tmp_path)
    assert web["worker"]["state"]=="running"
    assert len(web["worker"]["providers"])==6
    assert web["worker"]["providers"][1]["state"]=="blocked_permission"
    assert web["metrics"]["applications"] is None
    assert "upwork-application-history.json" not in json.dumps(web)


def test_monitor_repeated_tick_and_stale_display(tmp_path):
    run(tmp_path,when="2026-10-25T00:00:00+00:00")
    pub=build_public_payload(tmp_path)
    assert pub["worker"]["state"]=="stale"
    status=run(tmp_path)
    assert status["native_submitted_total"]==0
    assert build_public_payload(tmp_path)["worker"]["state"]=="running"
