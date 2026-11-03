"""Persistent application supervisor. Official API dispatch is permission-gated.

This process runs without a browser, never bypasses login/captcha/KYC, and
cannot count a proposal as submitted without a native provider bid receipt.
Freelancer.com's written permission is mandatory for automation. No Upwork
Connects are consumed here: its MCP requires per-proposal confirmation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

STATES = ("ready", "blocked", "sending_unknown", "submitted_verified", "skipped")
DDL = """
CREATE TABLE IF NOT EXISTS dispatch_attempts(
    provider TEXT NOT NULL, external_job_id TEXT NOT NULL,
    title TEXT NOT NULL, bid_amount REAL NOT NULL,
    draft TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT,
    reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY(provider,external_job_id)
);
CREATE INDEX IF NOT EXISTS ix_dispatch_state
 ON dispatch_attempts(state,updated_at);
"""
LANGUAGE_EXCLUDE = re.compile(
    r"(english[\s/-]+(?:portuguese|spanish|hindi|arabic|french|german)"
    r"|(?:portuguese|spanish|hindi|arabic|french|german)[\s/-]+english"
    r"|(?:portuguese|spanish|hindi|arabic|french|german) translation"
    r"|university document translation|voice recording|native speaker "
    r"(?!japanese)|cold call|telemarketing|human only|no ai allowed"
    r"|captcha|review boost|fake review|essay writing|ghostwrit"
    r"|adult|crypto trading|casino|unlimited free trial|appointment bot|bulk marketing|right hand|long-term)", re.I
)
DELIVERY_TITLES = re.compile(
    r"(excel|spreadsheet|google sheets|python|web scraper|data clean"
    r"|data extraction|csv|pdf to excel|api integrat|n8n|automation"
    r"|workflow|power query|vba)", re.I
)
# Only demonstrable skills and a digital, fixed-price task, not endless employment.
SPECIALIST = (
    ("excel", "Excel formulas, a clear input sheet, and checks that catch invalid entries"),
    ("spreadsheet", "a maintainable spreadsheet with validation and a short handover"),
    ("python", "a reproducible Python implementation, input/output examples, and tests"),
    ("api", "a documented API integration with validation, error handling and test cases"),
    ("automation", "a controlled automation workflow with retry rules and a handover"),
    ("csv", "a clean CSV output with a reproducible transformation and verification checks"),
    ("data extraction", "an accurate data extract with source references and QA checks"),
    ("n8n", "an n8n workflow with documented triggers, failure paths and a test run"),
)
TARGET = 100


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic(path: Path, obj: dict) -> None:
    t=path.with_suffix(path.suffix + ".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(t,path)


def gates(env: dict[str,str] | None = None) -> dict:
    env=os.environ if env is None else env
    keys=(
        "FLN_API_WRITTEN_PERMISSION",
        "FLN_AUTOBID_ENABLED",
        "FLN_PROFILE_VERIFIED",
    )
    flags={key:env.get(key,"").lower() in ("true","1","yes") for key in keys}
    token_present=bool(env.get("FLN_OAUTH_TOKEN"))
    flags["FLN_OAUTH_TOKEN_PRESENT"]=token_present
    return {
        "authorized":all(flags.values()),
        "missing":[k for k,v in flags.items() if not v],
        "policy":"Freelancer.com written API-automation permission and official OAuth required",
    }


def qualify(row: dict) -> dict | None:
    title=str(row.get("title") or "")
    description=str(row.get("description") or "")
    raw=json.loads(row.get("raw_json") or "{}")
    if (row.get("source")!="freelancer_public"
        or not re.fullmatch(r"\d{5,12}",str(row.get("external_id") or ""))
        or not DELIVERY_TITLES.search(title)
        or LANGUAGE_EXCLUDE.search(title+" "+description[:500])
        or len(description.strip())<95
        or "fixed" not in str(row.get("contract_type") or "").lower()
        or "freelancer.com/projects/" not in str(row.get("url") or "")
        or raw.get("project_status")!="active"):
        return None
    bid_count=raw.get("bid_count")
    if isinstance(bid_count,int) and bid_count>95:
        return None
    currency=raw.get("budget_currency","USD")
    minimums={"USD":15, "EUR":15, "GBP":15, "AUD":20,
              "INR":500, "JPY":3000}
    if currency not in minimums:
        return None
    compensation=str(row.get("compensation") or "")
    matched=re.search(r"([A-Z]{3})\s+([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)",compensation)
    if not matched or matched.group(1)!=currency:
        return None
    low=float(matched.group(2).replace(",",""))
    high=float(matched.group(3).replace(",",""))
    if not minimums[currency] <= low <= high <= 2000000:
        return None
    posted=row.get("published_at")
    if posted:
        try:
            stamp=datetime.fromisoformat(str(posted).replace("Z","+00:00"))
            if stamp.tzinfo is None or not (-600 < (datetime.now(timezone.utc)-stamp).total_seconds() < 14*86400):
                return None
        except ValueError:
            return None
    skill=next((value for word,value in SPECIALIST if word in title.lower()),
               "the requested digital deliverable with input validation and documentation")
    amount=min(high,max(low,round(low*1.1,2)))
    # Titles and descriptions are untrusted. Never promise a finished product
    # or claim prior client results and don't copy entire client text into a bid.
    title_clean=re.sub(r"\s+"," ",title).strip()[:110]
    draft=(f"Hello,\n\nI reviewed your {title_clean} project. "
           f"I can deliver {skill}. "
           "I work with Python, Excel and business process automation. "
           "For this job I would first confirm the input format and expected "
           "output, build a small working example, verify edge cases and "
           "provide setup instructions.\n\n"
           f"My fixed-price proposal is {currency} {amount:g}, subject to confirming "
           "the final scope and source-data permissions. "
           "Could you share a representative input and what you will check "
           "at acceptance? That will help me confirm the delivery date.\n\nThanks.")
    return {"project_id":int(row["external_id"]),"title":title_clean,
            "amount":amount,"currency":currency,"draft":draft,"bid_count":bid_count}


def load_candidates(root: Path) -> tuple[list[dict],int]:
    qpath=root/"application-intents.db"
    dbpath=root/"jobs.db"
    if not qpath.exists() or not dbpath.exists():
        return [],0
    q=sqlite3.connect(qpath,timeout=20)
    q.row_factory=sqlite3.Row
    j=sqlite3.connect(dbpath,timeout=20)
    j.row_factory=sqlite3.Row
    try:
        pending=q.execute(
            "SELECT external.job_hash, external.job_url, external.title, external.status "
            "FROM application_intents external "
            "WHERE external.source='freelancer_public' "
            "AND external.status IN ('qualification_pending','draft_ready','provider_authorization_required')"
        ).fetchall()
        checked=[]
        for rec in pending:
            r=j.execute(
                "SELECT source, external_id, title, description, compensation, "
                "contract_type, url, raw_json, published_at FROM jobs WHERE url=?",
                (rec["job_url"],)
            ).fetchone()
            if r is not None:
                item=qualify(dict(r))
                if item:
                    item["job_hash"]=rec["job_hash"]
                    checked.append(item)
        checked.sort(key=lambda x:(x["bid_count"] if isinstance(x["bid_count"],int) else 100,
                                  -x["project_id"]))
        return checked,len(pending)
    finally:
        q.close()
        j.close()


def sdk_send(proposal: dict, env: dict[str,str]|None=None) -> str:
    """Provider-native endpoint via published official Python SDK; no silent retry."""
    env=os.environ if env is None else env
    if not gates(env)["authorized"]:
        raise PermissionError("provider_permission_or_oauth_missing")
    from freelancersdk.session import Session
    from freelancersdk.resources.users import get_self_user_id
    from freelancersdk.resources.projects import place_project_bid
    # Important: production only; never send to unknown domains or use cookies.
    session=Session(oauth_token=env["FLN_OAUTH_TOKEN"],
                    url="https://www.freelancer.com")
    me=get_self_user_id(session)
    if not isinstance(me,int) or me<=0:
        raise RuntimeError("provider_account_unverified")
    bid=place_project_bid(
        session,project_id=proposal["project_id"],bidder_id=me,
        amount=proposal["amount"],period=3,milestone_percentage=100,
        description=proposal["draft"],
    )
    if isinstance(bid,dict):
        bid_id=bid.get("id") or (bid.get("result") or {}).get("id")
    else:
        bid_id=getattr(bid,"id",None)
    if not str(bid_id or "").isdigit():
        raise RuntimeError("provider_bid_receipt_unconfirmed")
    return str(bid_id)


def run(root: Path, *, env: dict[str,str]|None=None,
        send: Callable[[dict],str]|None=None) -> dict:
    root.mkdir(parents=True,exist_ok=True)
    flags=gates(env)
    eligible,scanned=load_candidates(root)
    now_str=now()
    conn=sqlite3.connect(root/"application-dispatch.db",timeout=20)
    conn.execute("PRAGMA busy_timeout=20000")
    conn.executescript(DDL)
    sent_this_run=0
    errors=0
    inspected=0
    try:
        sent_today=conn.execute(
            "SELECT COUNT(*) FROM dispatch_attempts "
            "WHERE state='submitted_verified' AND updated_at>=?",
            (datetime.now(timezone.utc).date().isoformat(),)
        ).fetchone()[0]
        for item in eligible:
            pid=str(item["project_id"])
            prior=conn.execute(
                "SELECT state FROM dispatch_attempts WHERE provider=? AND external_job_id=?",
                ("freelancer",pid)
            ).fetchone()
            if prior:
                # Only a blocked, never-attempted row can advance when
                # provider approval becomes valid. Unknown/submitted never retry.
                if prior[0]!="blocked" or not flags["authorized"]:
                    continue
            else:
                if inspected>=15:
                    break
                inspected+=1
            if flags["authorized"] and (sent_this_run>=1 or sent_today>=3):
                continue
            state="ready" if flags["authorized"] else "blocked"
            reason="" if flags["authorized"] else "provider_oauth_or_written_permission_missing"
            if prior:
                conn.execute(
                    "UPDATE dispatch_attempts SET state=?,reason=?,updated_at=? "
                    "WHERE provider=? AND external_job_id=? AND state='blocked'",
                    (state,reason,now_str,"freelancer",pid))
            else:
                conn.execute(
                    "INSERT INTO dispatch_attempts "
                    "(provider,external_job_id,title,bid_amount,draft,state,reason,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    ("freelancer",pid,item["title"],item["amount"],
                     item["draft"],state,reason,now_str,now_str))
            conn.commit()
            if state!="ready":
                continue
            # In-doubt before making a write call, fail closed if process dies.
            conn.execute(
                "UPDATE dispatch_attempts SET state='sending_unknown',updated_at=? "
                "WHERE provider=? AND external_job_id=?",
                (now(),"freelancer",pid)
            )
            conn.commit()
            try:
                receipt=(send or (lambda p:sdk_send(p,env)))(item)
                if not isinstance(receipt,str) or not re.fullmatch(r"\d{3,30}",receipt):
                    raise ValueError("native_receipt_missing")
            except Exception as exc:
                # Do not retry automatically. The platform might have accepted it.
                errors+=1
                conn.execute(
                    "UPDATE dispatch_attempts SET reason=?,updated_at=? "
                    "WHERE provider='freelancer' AND external_job_id=?",
                    ("outcome_unknown:"+type(exc).__name__,now(),pid)
                )
                conn.commit()
                break
            else:
                conn.execute(
                    "UPDATE dispatch_attempts SET state='submitted_verified',receipt=?,reason='',updated_at=? "
                    "WHERE provider='freelancer' AND external_job_id=?",
                    (receipt,now(),pid)
                )
                conn.commit()
                sent_this_run+=1
                sent_today+=1
        rows=conn.execute(
            "SELECT state,COUNT(*) FROM dispatch_attempts GROUP BY state"
        ).fetchall()
        counts=dict(rows)
        latest=conn.execute(
            "SELECT title,bid_amount,state,updated_at FROM dispatch_attempts "
            "ORDER BY updated_at DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()
    # This file has only numeric summaries, no secrets, bids, project IDs or drafts.
    platforms=[
        {"name":"Upwork","mode":"official_mcp","state":"requires_individual_confirmation",
         "reason":"Official ChatGPT MCP confirmation/Connects; no unattended browser bot"},
        {"name":"Freelancer.com","mode":"official_sdk","state":"authorized" if flags["authorized"] else "blocked_permission",
         "reason":"native_bid_send_enabled" if flags["authorized"] else flags["missing"][0],
         "queued":len(eligible)},
        {"name":"CrowdWorks","mode":"web_account","state":"blocked_account",
         "reason":"No documented freelancer bid API; native logged-in form required"},
        {"name":"Lancers","mode":"web_account","state":"blocked_account",
         "reason":"No authorized bid-write connector"},
        {"name":"Contra","mode":"web_account","state":"blocked_profile",
         "reason":"Profile/KYC not completed"},
        {"name":"LinkedIn","mode":"search_only","state":"blocked_apply",
         "reason":"People-search connector has no job application action"},
    ]
    status={
        "schema":1,"worker":"application-supervisor",
        "last_tick":now(),"process":"healthy","goal":TARGET,
        "candidate_queue":scanned,"high_fit_eligible":len(eligible),
        "drafts_created":sum(counts.values()),
        "dispatch_states":counts,"native_submitted_this_tick":sent_this_run,
        "native_submitted_total":counts.get("submitted_verified",0),
        "unknown_outcome":counts.get("sending_unknown",0),
        "errors_this_tick":errors,
        "providers":platforms,
        "pipeline":[
            {"stage":"discover","state":"scheduled","detail":"Source collection runs separately"},
            {"stage":"review","state":"running","detail":"Eligibility, language, budget, duplicate and scope checks"},
            {"stage":"draft","state":"running","detail":"Project-specific fixed-price drafts stored privately"},
            {"stage":"submit","state":"active" if flags["authorized"] else "blocked",
             "detail":"Official API only, max 1/run and 3/day, permission required"},
            {"stage":"verify","state":"running","detail":"Provider bid receipt ID or unknown outcome; no fabricated submissions"},
        ],
    }
    _atomic(root/"application-supervisor-status.json",status)
    return status


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True)
    args=parser.parse_args()
    result=run(Path(args.root))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
