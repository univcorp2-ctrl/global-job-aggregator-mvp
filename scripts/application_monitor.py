"""Read-only application operations heartbeat for the public dashboard.

Runs in Windows Task Scheduler without any browser, provider API request, bid,
message or user-token read. Submitted counts come from native receipts stored
by separately authorized providers, never from a draft or queue.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}


def queue_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro",uri=True,timeout=8) as db:
            return db.execute(
                "SELECT COUNT(*) FROM application_intents "
                "WHERE status IN ('qualification_pending','draft_ready',"
                "'provider_authorization_required','provider_confirmation_required')"
            ).fetchone()[0]
    except sqlite3.Error:
        return 0


def dispatch_counts(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro",uri=True,timeout=8) as db:
            return dict(db.execute(
                "SELECT state, COUNT(*) FROM dispatch_attempts GROUP BY state"
            ).fetchall())
    except sqlite3.Error:
        return {}


def run(root: Path, *, when: str | None=None) -> dict:
    root.mkdir(parents=True,exist_ok=True)
    existing=read_json(root/"application-supervisor-status.json")
    qcount=queue_size(root/"application-intents.db")
    counts=dispatch_counts(root/"application-dispatch.db")
    verified=read_json(root/"upwork-application-history.json")
    count_upwork=sum(1 for r in verified.get("entries",[])
                    if isinstance(r,dict) and r.get("status")=="submitted"
                    and r.get("provider_status_label")=="Submitted")
    # Never infer OAuth/permission from a token stored on disk. This monitor
    # cannot enable the bid adapter or make an external submission.
    status={
        "schema":1,"worker":"application-monitor",
        "last_tick":when or iso(),"process":"healthy",
        "execution_mode":"read_only_review_and_audit",
        "goal":100,
        "candidate_queue":qcount,
        "high_fit_eligible":int(existing.get("high_fit_eligible",0)),
        "drafts_created":sum(counts.values()),
        "dispatch_states":counts,
        "native_submitted_this_tick":0,
        "native_submitted_total":counts.get("submitted_verified",0),
        "official_upwork_submitted":count_upwork,
        "unknown_outcome":counts.get("sending_unknown",0),
        "providers":[
            {"name":"Upwork","state":"requires_individual_confirmation"},
            {"name":"Freelancer.com","state":"blocked_permission","queued":qcount},
            {"name":"CrowdWorks","state":"blocked_account"},
            {"name":"Lancers","state":"blocked_account"},
            {"name":"Contra","state":"blocked_profile"},
            {"name":"LinkedIn","state":"blocked_apply"},
        ],
    }
    dest=root/"application-supervisor-status.json"
    temporary=dest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(temporary,dest)
    return status


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    args=p.parse_args()
    print(json.dumps(run(Path(args.root)),ensure_ascii=False))


if __name__=="__main__":
    main()
