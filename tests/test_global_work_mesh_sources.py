"""Source provenance and public-vs-private application state regressions."""
from __future__ import annotations

import json
from pathlib import Path

from app.core import connect, init_db
from scripts.global_work_mesh import export


def _record(db: Path, *, source: str, external_id: str, url: str,
            raw_json: str = "{}") -> None:
    with connect(db) as c:
        c.execute(
            """INSERT INTO jobs
            (source,external_id,title,company,url,location,description,
             contract_type,compensation,published_at,fetched_at,raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (source,external_id,"Spreadsheet data cleanup","Company",
             url,"Remote","Fixed price Excel","contract","$50",
             "2026-10-28T10:00:00+00:00","2026-10-28T11:00:00+00:00",raw_json))


def test_public_source_counts_and_unverified_queue_are_separate(tmp_path):
    db=tmp_path/"jobs.db"
    init_db(db)
    _record(db,source="jobicy",external_id="one",
            url="https://jobicy.com/jobs/sample-job")
    _record(db,source="himalayas",external_id="two",
            url="https://himalayas.app/jobs/old",
            raw_json=json.dumps({"applicationLink":"https://himalayas.app/jobs/sample-two"}))
    _record(db,source="upwork",external_id="three",
            url="https://www.upwork.com/jobs/~02DO_NOT_PUBLISH")
    (tmp_path/"status.json").write_text(json.dumps({
        "application_prequalified":46,"real_application_count":0}),encoding="utf-8")
    dest=tmp_path/"public"
    payload=export(db,dest)
    assert payload["schema"]==1
    assert payload["listing_count"]==2
    assert payload["source_counts"]=={"Himalayas":1,"Jobicy":1}
    assert payload["auto_apply"]["prequalified"]==0
    assert payload["auto_apply"]["screening_queue_unverified"]==46
    assert payload["auto_apply"]["upwork_official_proposals_not_synced"] is True
    assert payload["verified_freelance_job_count"]==0
    assert payload["employment_or_unverified_count"]>=0
    assert len([x for x in payload["source_coverage"] if x["status"]=="published"])==2
    upwork=next(x for x in payload["source_coverage"] if x["name"]=="Upwork")
    assert upwork["status"]=="connected_private"
    assert upwork["listing_count"] is None
    exported=(dest/"jobs.json").read_text(encoding="utf-8")
    assert "DO_NOT_PUBLISH" not in exported
    assert "jobs/sample-two" in exported
    assert set(p.name for p in dest.iterdir())=={
        "_headers","app.js","index.html","style.css","jobs.json"}


def test_public_jobs_discard_wrong_domain_and_duplicates(tmp_path):
    db=tmp_path/"jobs.db"
    init_db(db)
    _record(db,source="jobicy",external_id="one",
            url="https://jobicy.com/jobs/same")
    _record(db,source="jobicy",external_id="two",
            url="https://jobicy.com/jobs/same")
    _record(db,source="jobicy",external_id="three",
            url="https://phishing.example/private")
    payload=export(db,tmp_path/"public")
    assert payload["listing_count"]==1
    assert payload["source_counts"]["Jobicy"]==1
    assert payload["source_counts"]["Himalayas"]==0
