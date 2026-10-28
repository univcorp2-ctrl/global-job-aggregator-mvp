"""Owner-only application intake and delivery routing.

No platform dispatch is implemented. A local draft is NOT a proposal.
An actual submitted application is recorded only from official platform readback.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.workers import WorkerConnection

DDL = """
CREATE TABLE IF NOT EXISTS application_queue (
 id TEXT PRIMARY KEY,
 platform TEXT NOT NULL,
 external_job_id TEXT NOT NULL,
 title TEXT NOT NULL,
 job_url TEXT NOT NULL,
 budget_amount REAL NOT NULL,
 currency TEXT NOT NULL,
 application_credits INTEGER NOT NULL DEFAULT 0,
 expected_ai_tasks_json TEXT NOT NULL,
 specialist_tasks_json TEXT NOT NULL,
 ai_first INTEGER NOT NULL DEFAULT 1,
 subcontract_permission TEXT NOT NULL DEFAULT 'unknown',
 draft_text TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL,
 blocked_reason TEXT NOT NULL DEFAULT '',
 evidence TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(platform,external_job_id)
);
CREATE INDEX IF NOT EXISTS idx_application_status ON application_queue(status, updated_at);
"""

def connect_queue(path: str | Path) -> sqlite3.Connection:
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(p),factory=WorkerConnection)
    db.row_factory=sqlite3.Row
    db.executescript(DDL)
    return db

def verify_job_url(platform: str, url: str) -> str:
    parsed=urlparse(url)
    hosts={"upwork":("upwork.com",),"freelancer":("freelancer.com",),
           "contra":("contra.com",),"opt_in":()}
    if platform not in hosts or parsed.scheme!="https" or not parsed.hostname:
        raise ValueError("Verified HTTPS platform URL required")
    if hosts[platform] and not any(parsed.hostname==h or parsed.hostname.endswith("."+h) for h in hosts[platform]):
        raise ValueError("Job URL host does not belong to its platform")
    return url

def add_candidate(
 db: sqlite3.Connection, *,
 platform: str, external_job_id: str, title: str, job_url: str,
 budget_amount: float, application_credits: int, currency: str = "USD",
 expected_ai_tasks: list[str] | None = None,
 specialist_tasks: list[str] | None = None,
 subcontract_permission: str = "unknown",
 draft_text: str = "",
) -> dict:
    if not title.strip() or not external_job_id.strip():
        raise ValueError("Missing job identifier or title")
    if len(title)>200 or len(draft_text)>5000 or len(external_job_id)>120:
        raise ValueError("Oversized candidate")
    if budget_amount<0 or budget_amount>1e8 or application_credits<0 or application_credits>500:
        raise ValueError("Invalid price or application credits")
    if subcontract_permission not in {"unknown","allowed","prohibited"}:
        raise ValueError("Unknown subcontract permission")
    tasks=[str(x).strip()[:160] for x in (expected_ai_tasks or []) if str(x).strip()][:20]
    specialist=[str(x).strip()[:160] for x in (specialist_tasks or []) if str(x).strip()][:20]
    if not tasks:
        raise ValueError("Must identify at least one AI-first deliverable")
    url=verify_job_url(platform,job_url)
    uid=hashlib.sha256((platform+":"+external_job_id).encode()).hexdigest()[:24]
    stage="draft_ready" if draft_text.strip() else "researched"
    now=datetime.now(timezone.utc).isoformat()
    db.execute("""
    INSERT INTO application_queue
    (id,platform,external_job_id,title,job_url,budget_amount,currency,
     application_credits,expected_ai_tasks_json,specialist_tasks_json,ai_first,
     subcontract_permission,draft_text,status,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(platform,external_job_id) DO UPDATE SET
      title=excluded.title,job_url=excluded.job_url,budget_amount=excluded.budget_amount,
      application_credits=excluded.application_credits,
      expected_ai_tasks_json=excluded.expected_ai_tasks_json,
      specialist_tasks_json=excluded.specialist_tasks_json,
      subcontract_permission=excluded.subcontract_permission,
      draft_text=excluded.draft_text,updated_at=excluded.updated_at
    """,(uid,platform,external_job_id,title,url,budget_amount,currency.upper(),
         application_credits,json.dumps(tasks),json.dumps(specialist),1,
         subcontract_permission,draft_text,stage,now,now))
    db.commit()
    return {"id":uid,"status":db.execute("SELECT status FROM application_queue WHERE id=?",(uid,)).fetchone()[0]}

def list_queue(db: sqlite3.Connection,limit:int=30) -> list[dict]:
    rows=db.execute("SELECT * FROM application_queue ORDER BY created_at DESC LIMIT ?",(min(max(limit,1),100),)).fetchall()
    result=[]
    for row in rows:
        rec=dict(row)
        rec["ai_tasks"]=json.loads(rec.pop("expected_ai_tasks_json"))
        rec["specialist_tasks"]=json.loads(rec.pop("specialist_tasks_json"))
        rec["ai_first"]=bool(rec["ai_first"])
        rec["is_submitted"]=rec["status"]=="submitted_verified"
        result.append(rec)
    return result

def plan_submission(db:sqlite3.Connection,uid:str,*,remaining_credits:int) -> dict:
    row=db.execute("SELECT * FROM application_queue WHERE id=?",(uid,)).fetchone()
    if row is None: raise ValueError("Candidate not found")
    if row["status"]=="submitted_verified":
        return {"status":"already_verified","submitted":True}
    reasons=[]
    if not row["draft_text"]:
        reasons.append("proposal_draft_missing")
    if row["application_credits"]>remaining_credits:
        reasons.append("insufficient_platform_credits")
    if row["specialist_tasks_json"]!="[]" and row["subcontract_permission"]!="allowed":
        reasons.append("external_specialist_work_requires_client_permission")
    return {
        "job_id":row["external_job_id"],
        "status":"blocked" if reasons else "awaiting_platform_preview_and_specific_approval",
        "reasons":reasons,
        "application_credits":row["application_credits"],
        "remaining_credits":remaining_credits,
        "sent":False,
        "submitted":False,
        "platform_action":"none",
        "needs_attachments_choice":True,
        "human_confirmation_required_for_each_preview":True,
        "specialist_not_contacted":True,
    }

def classify_delivery(*, specialist_tasks:list[str], subcontract_allowed:bool,
                      has_specialist_consent:bool=False, has_customer_data_permission:bool=False) -> dict:
    tasks=[x for x in specialist_tasks if x and x.strip()]
    if not tasks:
        return {"routing":"ai_first","may_outsource":False,"send_enabled":False,
                "next":"Deliver with automated tests and final QA; obtain client files safely"}
    allow=(subcontract_allowed and has_specialist_consent and has_customer_data_permission)
    return {
        "routing":"human_specialist_after_approval" if allow else "hold_specialist_tasks",
        "may_outsource":allow,
        "send_enabled":False,
        "next":("Owner reviews specialist quote and platform-native invite; no automatic order"
                if allow else "Get written client permission, specialist consent and data sharing rights"),
    }


def assess_job_constraints(description: str, *, ai_first: bool = True) -> dict:
    """Conservative screening of explicit client instructions.

    This catches clear English phrases only. A PASS is never proof that AI
    or subcontracting is allowed; absent explicit permission stays UNKNOWN.
    """
    import re
    text = " ".join(description.lower().split())
    ai_exclusions = [
      r"without (?:the use of )?(?:generative )?ai",
      r"do not use (?:generative )?ai",
      r"no (?:generative )?ai (?:tools|content|writing|allowed)",
      r"(?:final|all) (?:wording|documentation|text) must be written .*?without (?:generative )?ai",
      r"(?:human[- ]written|100% human[- ]written)",
      r"no chatgpt",
    ]
    outsource_exclusions = [
      r"no subcontract(?:ors|ing)?",
      r"subcontracting (?:is |strictly )?(?:prohibited|not allowed)",
      r"no (?:agencies|third[- ]party contractors)",
      r"work must be performed by (?:you|the applicant) personally",
    ]
    flags = {
        "explicit_no_ai": any(re.search(q, text) for q in ai_exclusions),
        "explicit_no_subcontract": any(re.search(q, text) for q in outsource_exclusions),
    }
    if flags["explicit_no_ai"] and ai_first:
        stage = "reject_ai_first"
    else:
        stage = "manual_scope_and_platform_review"
    return {
        "screening_state": stage,
        "flags": flags,
        "ai_use_rights": "prohibited" if flags["explicit_no_ai"] else "not_established",
        "subcontract_rights": "prohibited" if flags["explicit_no_subcontract"] else "not_established",
        "auto_send_enabled": False,
        "warning": "Keyword filter only; read full job terms and client instructions before proposing.",
    }
