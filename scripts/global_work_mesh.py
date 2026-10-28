"""Permission-aware public job catalog publisher.

Only public, attribution-permitted sources are published. Never expose scraped
Upwork/Contra listings, private offers, user profiles, API tokens or raw records.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from app.core import connect, init_db
from app.revenue_policy import triage

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web" / "global-work-mesh"
FILES = ("index.html", "app.js", "style.css", "_headers")
PROVIDERS = {"himalayas": ("Himalayas", "himalayas.app"),
             "jobicy": ("Jobicy", "jobicy.com")}

def clean(value, limit=120):
    return " ".join(str(value or "").split())[:limit]

def valid_link(url, host):
    if not isinstance(url, str) or len(url) > 1024:
        return False
    parts = urlsplit(url)
    return parts.scheme == "https" and (parts.hostname == host or
        (parts.hostname or "").endswith("." + host)) and not parts.username

def publishable_jobs(db_path, limit=120):
    init_db(db_path)
    results = []
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT source,title,company,url,description,location,contract_type,"
            "compensation,published_at,raw_json FROM jobs "
            "WHERE source IN ('himalayas','jobicy') "
            "ORDER BY COALESCE(published_at,fetched_at) DESC LIMIT ?", (limit*5,)
        ).fetchall()
    seen=set()
    for row in rows:
        src=row["source"]
        name,host=PROVIDERS[src]
        raw={}
        try: raw=json.loads(row["raw_json"] or "{}")
        except (TypeError,ValueError): pass
        if src=="himalayas":
            url=raw.get("applicationLink") if isinstance(raw,dict) else None
        else:
            url=row["url"]
        if not valid_link(url,host): continue
        if url in seen: continue
        seen.add(url)
        assessment=triage(row)
        results.append({
            "title":clean(row["title"],130),
            "company":clean(row["company"],70),
            "location":clean(row["location"],75),
            "source":name,
            "source_url":"https://"+host+"/",
            "url":url,
            "contract_type":clean(row["contract_type"],45),
            "compensation":clean(row["compensation"],65),
            "published_at":clean(row["published_at"],45),
            "ai_first":assessment["ai_only_candidate"],
            "kind":"digital_project_candidate" if assessment["project_qualified"] else "employment_or_unverified",
        })
        if len(results)>=limit: break
    return results

def export(db_path, dest):
    dest.mkdir(parents=True,exist_ok=True)
    for name in FILES: shutil.copyfile(ASSETS/name,dest/name)
    jobs=publishable_jobs(db_path)
    payload={
       "schema":1, "updated_at":datetime.now(timezone.utc).isoformat(),
       "listing_count":len(jobs),
       "sources":["Himalayas","Jobicy"],
       "rights":"Attribution-required, source-native apply links only; do not redistribute as API",
       "jobs":jobs,
       "connectors":[
         {"name":"Himalayas","mode":"public API","status":"public_search"},
         {"name":"Jobicy","mode":"public API and MCP","status":"public_search"},
         {"name":"Upwork","mode":"official MCP","status":"user_oauth_native_confirmation"},
         {"name":"Freelancer.com","mode":"official OAuth API","status":"oauth_not_verified"},
         {"name":"Contra","mode":"official MCP","status":"user_oauth_native_confirmation"},
         {"name":"Apify","mode":"Store API","status":"product_discovery_only"},
       ],
       "capabilities":{"search":True,"sort":True,"copy_ai_draft_prompt":True,
                       "external_apply":"open_original_provider",
                       "cross_platform_messages":False,
                       "auto_hire":False,"paid_order":False}
    }
    (dest/"jobs.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf8")
    allowed=set(FILES)|{"jobs.json"}
    assert {p.name for p in dest.iterdir()}==allowed
    text=(dest/"jobs.json").read_text(encoding="utf8")
    assert "raw_json" not in text and "external_id" not in text and "Bearer " not in text
    return payload

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--deploy",action="store_true")
    args=p.parse_args()
    root=Path(args.root)
    dest=root/"global-work-mesh-public"
    data=export(root/"jobs.db",dest)
    output={"listed":data["listing_count"],"providers":data["sources"],"deployment":"not_requested"}
    if args.deploy:
        executable=shutil.which("wrangler.cmd") or shutil.which("wrangler")
        if executable:
            flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
            try:
                done=subprocess.run([executable,"pages","deploy",str(dest),"--project-name",
                                     "global-work-mesh","--branch","main"],
                    timeout=135,capture_output=True,text=True,stdin=subprocess.DEVNULL,
                    env={**os.environ,"WRANGLER_SEND_METRICS":"false"},
                    creationflags=flags)
                output["deployment"]="success" if done.returncode==0 else "failed"
                output["exit_code"]=done.returncode
            except (OSError,subprocess.SubprocessError):
                output["deployment"]="failed"
        else: output["deployment"]="wrangler_missing"
    (root/"global-work-mesh-publish-status.json").write_text(json.dumps(output,ensure_ascii=False),encoding="utf8")
    print(json.dumps(output,ensure_ascii=False))
if __name__=="__main__":
    main()
