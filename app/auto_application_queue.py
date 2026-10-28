"""Persistent, idempotent AI-first application PREPARATION queue.

This worker cannot submit to providers without an approved official write adapter.
No browser/session-cookie automation; no blanket acceptance of Upwork proposal
terms or use of Connects. Every state is evidence-based.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from app.core import connect, init_db
from app.revenue_policy import triage

SCHEMA = """
CREATE TABLE IF NOT EXISTS application_intents(
  job_hash TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  job_url TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  last_evaluated_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN
    ('qualification_pending','draft_ready','provider_authorization_required',
     'provider_confirmation_required','submitted','awarded','rejected','expired')),
  draft TEXT,
  provider_receipt TEXT,
  acceptance_verified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS app_status_idx ON application_intents(status);
CREATE TABLE IF NOT EXISTS application_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_hash TEXT NOT NULL,
  event_at TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT NOT NULL
);
"""

def _now():
    return datetime.now(timezone.utc).isoformat()

def _safe_url(url):
    if not isinstance(url, str) or len(url) > 1200: return False
    p = urlsplit(url)
    return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password

def _key(source, url):
    return hashlib.sha256((source.lower() + "\n" + url).encode("utf8")).hexdigest()

def _draft(row):
    title = re.sub(r"\s+", " ", str(row.get("title") or ""))[:110]
    # Applicant experience, pricing and client requirements cannot be invented.
    return (
        "Hello, I'm interested in your digital deliverable project: " + title + ".\n\n"
        "I work with Python, data extraction, spreadsheets and API workflows. "
        "I can review the source material and prepare a reproducible solution "
        "with evidence and a brief handover, if the scope is suitable.\n\n"
        "Before pricing or committing, could you confirm the exact outputs, "
        "source-data access and rights, acceptance tests, deadline, and "
        "whether a fully automated deliverable is acceptable?\n\n"
        "I do not represent this as completed work or claim unverified past clients."
    )

def _state_for(row):
    assessment = triage(row)
    if not assessment["ai_only_candidate"]: return None
    if not _safe_url(row.get("url")): return None
    # These are syndicated employment feeds, not confirmed buyer freelance orders.
    # They may be qualified for further inspection but not automatic external submission.
    return "qualification_pending"

def prepare(db_path, queue_path, limit=50):
    init_db(db_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as upstream, sqlite3.connect(queue_path) as q:
        q.executescript(SCHEMA)
        upstream.row_factory=sqlite3.Row
        rows=upstream.execute(
            "SELECT source,title,url,description,contract_type,compensation,published_at "
            "FROM jobs ORDER BY COALESCE(published_at,fetched_at) DESC LIMIT 800"
        ).fetchall()
        n=0
        for raw in rows:
            row=dict(raw)
            state=_state_for(row)
            if state is None: continue
            job_hash=_key(str(row["source"]),str(row["url"]))
            old=q.execute(
                "SELECT status FROM application_intents WHERE job_hash=?", (job_hash,)
            ).fetchone()
            if old:
                q.execute("UPDATE application_intents SET last_evaluated_at=? "
                          "WHERE job_hash=?", (_now(),job_hash))
                continue
            if n >= limit: break
            q.execute(
                "INSERT INTO application_intents "
                "(job_hash,source,title,job_url,requested_at,last_evaluated_at,status,draft) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (job_hash,str(row["source"])[:40],str(row["title"])[:150],
                 str(row["url"])[:1200],_now(),_now(),state,_draft(row))
            )
            q.execute(
                "INSERT INTO application_events(job_hash,event_at,status,note) VALUES(?,?,?,?)",
                (job_hash,_now(),state,
                 "AI-first heuristic only; verify buyer order, provider write API and eligibility")
            )
            n+=1
        q.commit()
        summary={
            "evaluated":len(rows),
            "new_prequalified":n,
            "status_counts":{
                item[0]:item[1] for item in q.execute(
                    "SELECT status,COUNT(*) FROM application_intents GROUP BY status")
            },
            "external_submissions":q.execute(
                "SELECT COUNT(*) FROM application_intents WHERE status='submitted'"
            ).fetchone()[0],
            "awards":q.execute(
                "SELECT COUNT(*) FROM application_intents WHERE status='awarded'"
            ).fetchone()[0],
            "provider_write_enabled":False,
            "reason":"No independently approved write-scope provider credentials or explicit native confirmations",
        }
        return summary

def mark_submitted(q, job_hash, provider_receipt, *, official_adapter_verified=False):
    """Submission receipts can only be recorded by a verified official adapter."""
    if not official_adapter_verified:
        raise PermissionError("Unverified adapter cannot record an actual application")
    if not isinstance(provider_receipt,str) or len(provider_receipt.strip()) < 7:
        raise ValueError("Missing provider-native submission confirmation ID")
    existing=q.execute("SELECT status FROM application_intents WHERE job_hash=?",
                       (job_hash,)).fetchone()
    if not existing or existing[0] not in (
        "provider_authorization_required","provider_confirmation_required"):
        raise PermissionError("Unexpected application state; do not silently resubmit")
    q.execute("UPDATE application_intents SET status='submitted', provider_receipt=? "
              "WHERE job_hash=? AND status != 'submitted'",
              (provider_receipt,job_hash))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    args=p.parse_args()
    root=Path(args.root)
    summary=prepare(root/"jobs.db",root/"application-intents.db")
    path=root/"application-queue-status.json"
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"run_at":_now(),**summary},ensure_ascii=False,indent=2),
                   encoding="utf8")
    os.replace(tmp,path)
    print(json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    main()
