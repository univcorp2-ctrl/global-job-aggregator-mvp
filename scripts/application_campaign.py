"""Read-only batch intake for up to 100 actionable marketplace leads, NOT auto-bids.

Uses Freelancer.com's official public GET projects endpoint. Never uses cookies,
credential-bearing URLs, direct messaging or application POST. Separately records
provider-verified submitted applications via the existing guarded pipeline.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core import NormalizedJob, Settings, connect, init_db, upsert_job, strip_html
from app.revenue_policy import triage
from app.auto_application_queue import prepare

BASE = "https://www.freelancer.com/api/projects/0.1/projects/active/"
TERMS = (
    "Python", "Excel", "API integration", "automation", "Google Sheets",
    "data extraction", "Japanese", "n8n", "workflow", "VBA",
)
FIT = re.compile(
    r"\b(python|excel|spreadsheet|google sheets|vba|n8n|automation|"
    r"workflow|api|data extraction|data cleaning|data entry|japanese|"
    r"scraping|fastapi|pdf|chatbot|ai agent|machine learning)\b", re.I
)
TITLE_FIT = re.compile(
    r"(python|excel|spreadsheet|google sheets|vba|n8n|automation|"
    r"workflow|api|data extraction|data cleaning|japanese|"
    r"web scraping|fastapi|ai agent|pdf.{0,20}excel)", re.I
)
EXCLUDE = re.compile(
    r"(review[s]? boost|fake review|captcha|account sell|buy followers|"
    r"academic ghostwrit|thesis ghostwrit|remote access to personal|"
    r"telegram mass|bulk whatsapp spam|casino|gambling|"
    r"live call|cold call|adult|only native spanish|french translation|"
    r"arabic translation|hindi translation)", re.I
)
# This endpoint is a broad search: terms alone DO NOT qualify a project.
GOAL = 100


def normalize(record: dict) -> NormalizedJob | None:
    if not isinstance(record, dict) or record.get("status") != "active":
        return None
    ident = str(record.get("id") or "")
    title = str(record.get("title") or "").strip()
    seo = str(record.get("seo_url") or "")
    if not ident.isdigit() or not title or len(title) > 190:
        return None
    if not seo or ".." in seo or seo.startswith("/") or "://" in seo:
        return None
    skills = record.get("jobs") or []
    skill_names = " ".join(str(x.get("name") or x.get("seo_url") or "")
                           for x in skills if isinstance(x, dict))
    if not TITLE_FIT.search(title):
        return None
    if not FIT.search(skill_names + " " + title):
        return None
    desc = (strip_html(record.get("description")
                       or record.get("preview_description")) or "")[:5000]
    if EXCLUDE.search(title + " " + desc[:300]):
        return None
    budget = record.get("budget") or {}
    cur = record.get("currency") or {}
    money = str(cur.get("code") or "USD") if isinstance(cur, dict) else "USD"
    bmin = budget.get("minimum") if isinstance(budget, dict) else None
    bmax = budget.get("maximum") if isinstance(budget, dict) else None
    if not isinstance(bmin, (int, float)) or bmin < 1:
        return None
    if isinstance(bmax, (int, float)) and bmax < bmin:
        return None
    kind = "hourly" if record.get("type") == "hourly" else "fixed"
    bids = (record.get("bid_stats") or {}).get("bid_count")
    if isinstance(bids, int) and bids > 175:
        return None
    when = record.get("time_submitted") or record.get("submitdate")
    try:
        published = datetime.fromtimestamp(float(when),timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        published = None
    comp = f"{money} {bmin:g}"
    if isinstance(bmax, (int, float)):
        comp += f" - {bmax:g}"
    if kind == "hourly":
        comp += " /hr"
    row = NormalizedJob(
        source="freelancer_public", external_id=ident, title=title,
        company="", url="https://www.freelancer.com/projects/" + seo,
        description=desc, compensation=comp,
        contract_type=kind + " freelance project",remote="unknown",
        japan_ok="unknown",published_at=published,
        raw={"bid_count":bids,"budget_currency":money,"budget_type":kind,
             "project_status":"active","direct_bidding_eligible":"unverified"},
    )
    assessment=triage({"source":row.source, "title":row.title,
                       "description":row.description,
                       "contract_type":row.contract_type})
    if not assessment["ai_only_candidate"]:
        return None
    return row


async def collect(client: httpx.AsyncClient, *, pages: int = 3,
                  page_size: int = 25, target: int = GOAL) -> tuple[list[NormalizedJob],dict]:
    found: dict[str, NormalizedJob] = {}
    attempts = errors = scanned = 0
    for term in TERMS:
        for offset in range(0, pages * page_size, page_size):
            attempts += 1
            try:
                r=await client.get(BASE,params={
                    "query":term,"limit":page_size,"offset":offset,
                    "full_description":"true"})
                r.raise_for_status()
                data=r.json()
                if data.get("status")!="success":
                    errors+=1
                    continue
                raw=data.get("result") or {}
                jobs=raw.get("projects") or []
                scanned+=len(jobs)
                for item in jobs:
                    normalized=normalize(item)
                    if normalized:
                        found[normalized.external_id]=normalized
                if len(jobs)<page_size or len(found)>=target:
                    break
            except (httpx.HTTPError, ValueError, TypeError):
                errors+=1
                break
            # Be polite to the official public API; no high concurrency.
            await asyncio.sleep(0.25)
        if len(found)>=target:
            break
    chosen=sorted(found.values(),key=lambda r: (
        (r.raw.get("bid_count") if isinstance(r.raw.get("bid_count"),int) else 175),
        -(int(r.external_id))
    ))[:target]
    return chosen,{"queries":len(TERMS),"api_get_calls":attempts,"api_errors":errors,
                   "raw_rows_scanned":scanned,"qualified_unique":len(found)}


def safe_write(path: Path, payload: dict):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)


async def run(root: Path, *, goal: int = GOAL, pages: int = 3) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(14.0),
        follow_redirects=False,
        headers={"User-Agent":"RevenueAgent/PublicAPIReadOnly/1.0"},
    ) as client:
        jobs,report=await collect(client,pages=pages,target=goal)
    db_path=root/"jobs.db"
    init_db(db_path)
    with connect(db_path) as db:
        newly=0
        for job in jobs:
            newly+=int(bool(upsert_job(db,job)))
    summary=prepare(db_path,root/"application-intents.db",limit=goal)
    # A queued draft is NOT an application: never count it in the 100-app target.
    payload={
        "run_at":datetime.now(timezone.utc).isoformat(),
        "goal_verified_applications":goal,
        "marketplace_source":"freelancer_public_official_GET",
        "marketplace_leads_scanned":report["raw_rows_scanned"],
        "qualified_unique":report["qualified_unique"],
        "selected_unique_leads":len(jobs),
        "db_upserts":newly,
        "queue_created_this_run":summary["new_prequalified"],
        "queue_total_by_status":summary["status_counts"],
        "confirmed_submissions_from_queue":summary["external_submissions"],
        "api_get_calls":report["api_get_calls"],
        "api_errors":report["api_errors"],
        "provider_bids_sent":0,
        "provider_write_enabled":False,
        "blocking_reasons":[
           "Provider-native authenticated proposal submission not yet authorized",
           "Freelancer account profile/email verification or restricted balance conditions",
           "Every proposal requires job-specific client and eligibility verification",
        ],
    }
    safe_write(root/"application-campaign-status.json",payload)
    # Private only: no job titles, URLs or personal contacts in public site.
    safe_write(root/"application-campaign-private-leads.json",{
        "updated_at":payload["run_at"],
        "status":"qualification_pending_not_submitted",
        "leads":[{"source":r.source,"id":r.external_id,"title":r.title,
                  "url":r.url,"bid_count":r.raw.get("bid_count"),
                  "compensation_as_advertised":r.compensation}
                 for r in jobs],
    })
    return payload


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--goal",type=int,default=GOAL)
    p.add_argument("--pages",type=int,default=3)
    args=p.parse_args()
    if not 1 <= args.goal <= 100 or not 1 <= args.pages <= 4:
        p.error("goal 1..100; pages 1..4")
    result=asyncio.run(run(Path(args.root),goal=args.goal,pages=args.pages))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
