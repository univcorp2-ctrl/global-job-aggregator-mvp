"""Privacy and status correctness for the public Cloudflare Pages operations view."""
import json
from datetime import datetime, timedelta, timezone

from scripts.revenue_dashboard import build_public_payload, export, SOURCES


def fake_scan(*, run_at, secret="PRIVATE_CLIENT_NAME"):
    return {
        "run_at": run_at,
        "jobs": {
            "source_counts": {"himalayas": 5},
            "shortlist": [{
                "title": secret, "external_id": "never-publish-job-123",
                "url": "https://secret.example.com", "client_email": "private@example.com",
                "proposal_draft": "secret customer info",
            }]
        },
        "collect": {"results": [
            {"source": name, "fetched": 10, "saved": 10, "error": None}
            for name in SOURCES
        ]},
        "mcp_catalog": {
            "status": {"state": "read_only_success", "count": 92},
            "candidates": [{"description": "secret MCP publisher"}] * 60
        },
        "apify_catalog": {
            "status": {"state": "read_only_success", "count": 51},
            "candidates": [{"id": "private_id"}] * 51
        },
        "external_calls": {"submissions": 0},
        "worker_contacts": [{"name": secret}],
        "Authorization": "Bearer SECRET_TOKEN"
    }


def test_status_publish_drops_jobs_people_urls_and_auth(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    report = fake_scan(run_at=now)
    (tmp_path / "latest.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "status.json").write_text(
        json.dumps({"status": "success", "last_run": now}), encoding="utf-8"
    )
    (tmp_path / "scan-20261027T170000Z.json").write_text(json.dumps(report),
                                                         encoding="utf-8")
    public = build_public_payload(tmp_path)
    encoded = json.dumps(public, ensure_ascii=False)
    assert public["metrics"]["jobs_fetched"] == 50
    assert public["metrics"]["sources_ok"] == 5
    assert public["metrics"]["candidates"] == 1
    assert public["metrics"]["mcp_found"] == 92
    assert public["metrics"]["mcp_indexed"] == 60
    assert public["metrics"]["apify_found"] == 51
    assert sum(stage["done"] for stage in public["stages"]) == 4
    assert len(public["history"]) == 1
    assert all(mark not in encoded for mark in [
        "PRIVATE_CLIENT_NAME", "never-publish-job-123", "private@example.com",
        "secret customer info", "Bearer", "private_id", "external_id",
        "secret.example.com", "Authorization"
    ])
    assert public["metrics"]["contracts"] == public["metrics"]["revenue_jpy_verified"] == 0


def test_failure_error_messages_get_discarded(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    scan = fake_scan(run_at=now)
    scan["collect"]["results"][0]["error"] = (
        "HTTPStatusError: private endpoint https://secret.example.com?token=SECRET_TOKEN")
    (tmp_path / "latest.json").write_text(json.dumps(scan), encoding="utf-8")
    (tmp_path / "status.json").write_text(
        json.dumps({"status": "success", "last_run": now}), encoding="utf-8"
    )
    public = build_public_payload(tmp_path)
    assert public["metrics"]["sources_ok"] == 4
    assert public["sources"][0]["error_type"] == "HTTPStatusError"
    assert "SECRET_TOKEN" not in json.dumps(public)


def test_old_scan_is_not_reported_as_live(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat()
    (tmp_path / "latest.json").write_text(
        json.dumps(fake_scan(run_at=old)), encoding="utf-8")
    (tmp_path / "status.json").write_text(
        json.dumps({"status": "success", "last_run": old}), encoding="utf-8")
    result = build_public_payload(tmp_path)
    assert result["health"] == "offline"
    assert result["stages"][1]["done"] is False


def test_export_contains_only_allowlisted_assets(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    (tmp_path / "latest.json").write_text(json.dumps(fake_scan(run_at=now)),
                                                 encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"status": "success"}),
                                                 encoding="utf-8")
    target = tmp_path / "public-site"
    export(tmp_path, target)
    assert {p.name for p in target.iterdir()} == {
        "index.html", "app.js", "style.css", "_headers", "status.json"
    }
    assert "PRIVATE_CLIENT_NAME" not in (target / "status.json").read_text("utf-8")
