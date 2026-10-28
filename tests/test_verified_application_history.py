"""Submitted proposals are durable evidence; no client/private data in public site."""
import json
from datetime import datetime, timedelta, timezone

from scripts.revenue_dashboard import build_public_payload, _verified_submission_history


def verified_record(proposal_id="2115438119546572801"):
    return {
        "platform":"upwork",
        "proposal_id":proposal_id,
        "job_id":"2114428650485207954",
        "job_title":"Excel Tournament Draw",
        "job_url":"https://www.upwork.com/jobs/~022114428650485207954",
        "bid_amount":50,
        "bid_currency":"USD",
        "connects_spent":10,
        "status":"submitted",
        "provider_status":"Accepted",
        "provider_status_label":"Submitted",
        "submitted_at":"2026-10-28T13:38:45.296Z",
        "source":"Upwork official MCP",
        "private_cover_letter":"PRIVATE_LETTER_NOT_FOR_PUBLICATION",
        "oauth_token":"TOP_SECRET"
    }


def store(root, rows):
    (root/"upwork-application-history.json").write_text(
        json.dumps({"schema":1,"verification_source":"Upwork official MCP",
                    "entries":rows}), encoding="utf-8")


def test_verified_application_1_of_100_persists_when_session_stale(tmp_path):
    store(tmp_path,[verified_record(), verified_record()])
    (tmp_path/"upwork-application-verification.json").write_text(
        json.dumps({"provider":"upwork_official_mcp",
                    "verified_at":(datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),
                    "submitted":0,"connects_balance":12}),
        encoding="utf-8")
    output=build_public_payload(tmp_path)
    assert output["application_goal"]["verified_submitted"] == 1
    assert output["metrics"]["applications"] == 1
    assert output["stages"][4]["done"] is True
    assert len(output["application_history"]) == 1
    line=output["application_history"][0]
    assert line == {
        "platform":"Upwork","title":"Excel Tournament Draw",
        "submitted_at":"2026-10-28T13:38:45.296000+00:00",
        "status":"Submitted","bid_usd":50,"connects_spent":10
    }
    public=json.dumps(output, ensure_ascii=False)
    for forbidden in ("2115438119546572801","2114428650485207954",
                      "PRIVATE_LETTER_NOT_FOR_PUBLICATION","TOP_SECRET",
                      "oauth_token", "job_url", "proposal_id", "~022114428650485207954"):
        assert forbidden not in public


def test_draft_pending_and_forged_receipt_never_count(tmp_path):
    fake=verified_record()
    fake["status"]="preview_prepared_not_submitted"
    forged=verified_record("bad-job-id")
    unsupported=verified_record("2115438119546572802")
    unsupported["provider_status_label"]="Pending"
    injected=verified_record("2115438119546572803")
    injected["job_title"]="<script>alert(1)</script>"
    store(tmp_path,[fake,forged,unsupported,injected])
    assert _verified_submission_history(tmp_path)==[]
    pub=build_public_payload(tmp_path)
    assert pub["application_history"]==[]
    assert pub["application_goal"]["verified_submitted"] is None


def test_provider_must_be_authenticated_source(tmp_path):
    row=verified_record()
    (tmp_path/"upwork-application-history.json").write_text(
        json.dumps({"schema":1,"verification_source":"local-guessed","entries":[row]}),
        encoding="utf-8")
    assert _verified_submission_history(tmp_path)==[]
