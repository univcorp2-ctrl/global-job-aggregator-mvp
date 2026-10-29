"""Regression for a dashboard that once deployed a broken app.js despite HTTP 200."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from scripts.revenue_dashboard import build_public_payload


def test_public_dashboard_javascript_parses():
    exe=shutil.which("node")
    if not exe:
        pytest.skip("Node.js unavailable")
    script=Path(__file__).resolve().parents[1]/"web"/"revenue-agent"/"app.js"
    result=subprocess.run([exe,"--check",str(script)],
                          capture_output=True,text=True,timeout=12)
    assert result.returncode==0,result.stderr


def test_gmail_verified_application_plus_upwork_proposal_counts_two(tmp_path):
    submitted="2026-10-29T00:16:54+00:00"
    (tmp_path/"email-application-history.json").write_text(json.dumps({
        "schema":1,"verification_source":"Gmail SENT",
        "entries":[{
            "platform":"application_email",
            "source":"Gmail SENT verified",
            "gmail_message_id":"1a185044e2fd9f36",
            "organization":"Inflow Ltd",
            "job_title":"Automation Specialist",
            "job_url":"https://www.inflowconsulting.eu/careers",
            "recipient":"info@inflowconsulting.eu",
            "subject":"Application - Automation Specialist",
            "status":"sent_verified","submitted_at":submitted,
            "private_body":"SUPER_SECRET_BODY"
        }]
    }),encoding="utf-8")
    (tmp_path/"upwork-application-history.json").write_text(json.dumps({
        "schema":1,"verification_source":"Upwork official MCP",
        "entries":[{
            "platform":"upwork","proposal_id":"2115438119546572801",
            "job_title":"Excel Tournament Draw","status":"submitted",
            "provider_status_label":"Submitted",
            "submitted_at":"2026-10-28T13:38:45.296Z",
            "bid_amount":50,"connects_spent":10
        }]
    }),encoding="utf-8")
    pub=build_public_payload(tmp_path)
    assert pub["application_goal"]["verified_submitted"]==2
    assert pub["metrics"]["applications"]==2
    assert len(pub["application_history"])==2
    assert pub["application_history"][0]["platform"]=="Email応募"
    assert pub["application_history"][1]["platform"]=="Upwork"
    text=json.dumps(pub,ensure_ascii=False)
    for secret in ["1a185044e2fd9f36","info@inflowconsulting.eu",
                   "SUPER_SECRET_BODY","2115438119546572801"]:
        assert secret not in text


def test_draft_email_and_no_sent_proof_cannot_count(tmp_path):
    (tmp_path/"email-application-history.json").write_text(json.dumps({
        "schema":1,"verification_source":"Gmail SENT",
        "entries":[{"platform":"application_email",
                    "gmail_message_id":"1a185044e2fd9f36",
                    "status":"draft","submitted_at":"2026-10-29T00:16:54Z",
                    "source":"Gmail SENT verified"}]}),encoding="utf-8")
    pub=build_public_payload(tmp_path)
    assert pub["application_history"]==[]
    assert pub["application_goal"]["verified_submitted"] is None
