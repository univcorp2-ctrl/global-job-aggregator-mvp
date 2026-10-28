"""Public aggregate dashboard export and Cloudflare Pages publication.

Only a strict allowlist of numeric counters, source names and fixed text is published.
Private jobs, workers, tokens, job URLs, offers and whole raw scan files NEVER leave Drive.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_SOURCE = ROOT / "web" / "revenue-agent"
PROJECT = "revenue-agent-ops"
SOURCES = ("himalayas", "jobicy", "arbeitnow", "remotive", "remoshift", "freelancer_public")
SOURCE_NAMES = {"himalayas": "Himalayas", "jobicy": "Jobicy",
                "arbeitnow": "Arbeitnow", "remotive": "Remotive",
                "remoshift": "Remoshift", "freelancer_public": "Freelancer.com"}
MAX_HISTORY = 18
PUBLIC_FILES = ("index.html", "app.js", "style.css", "_headers")

def _number(value: object, limit: int = 1000000) -> int:
    try:
        if isinstance(value, bool):
            return 0
        value = int(value)
        return min(max(value, 0), limit)
    except (ValueError, TypeError, OverflowError):
        return 0

def _safe_iso(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 45:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat() if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None

def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}

def _upwork_verification(root: Path) -> dict:
    """Strictly public-safe, time-bounded summary of a separately verified API read.

    Never derive a submission from a draft, browser click, or Connects balance.
    In the absence of a fresh official-MCP readback, show *unverified*, not 0.
    """
    raw = _load(root / "upwork-application-verification.json")
    stamp = _safe_iso(raw.get("verified_at"))
    if raw.get("provider") != "upwork_official_mcp" or not stamp:
        return {"verification": "unverified", "verified_at": None,
                "submitted": None, "pending": None, "invitations": None,
                "connects_balance": None, "target": "unverified",
                "target_connects_cost": None, "target_open": None}
    age = (datetime.now(timezone.utc) -
           datetime.fromisoformat(stamp)).total_seconds()
    current = 0 <= age < 24 * 3600
    status = raw.get("target_status")
    target = status if status in {"not_submitted", "submitted", "closed"} else "unverified"
    # Values are snapshot counters, not live streaming updates. Do not make fake claims.
    return {"verification": "recent" if current else "stale", "verified_at": stamp,
            "submitted": _number(raw.get("submitted"), 100000) if current else None,
            "pending": _number(raw.get("pending"), 100000) if current else None,
            "invitations": _number(raw.get("invitations"), 100000) if current else None,
            "connects_balance": _number(raw.get("connects_balance"), 100000) if current else None,
            "target": target,
            "target_connects_cost": _number(raw.get("target_connects_cost"), 1000)
                                   if current else None,
            "target_open": bool(raw.get("target_open")) if current else None}


def _sources(report: dict) -> list[dict]:
    by_name = {str(r.get("source")): r for r in report.get("collect", {}).get("results", [])
               if isinstance(r, dict)} if isinstance(report.get("collect"), dict) else {}
    out = []
    for code in SOURCES:
        item = by_name.get(code, {})
        error = item.get("error")
        # Never leak exception messages or remote response/URLs into public HTML.
        error_type = str(error).split(":", 1)[0].strip() if isinstance(error, str) else None
        error_type = error_type if error_type in (
            "ProgrammingError", "ReadTimeout", "ConnectError", "HTTPStatusError",
            "ConnectTimeout", "TimeoutException", "ValueError", "JSONDecodeError",
        ) else ("Error" if error else None)
        state = "unavailable" if not item else ("error" if error else "ok")
        out.append({"id": code, "name": SOURCE_NAMES[code],
                    "state": state, "fetched": _number(item.get("fetched")),
                    "saved": _number(item.get("saved")), "error_type": error_type})
    return out

def _run_series(root: Path) -> list[dict]:
    points = []
    for f in sorted(root.glob("scan-*.json"), reverse=True)[:MAX_HISTORY]:
        r = _load(f)
        ts = _safe_iso(r.get("run_at"))
        if not ts:
            continue
        sources = _sources(r)
        points.append({
            "at": ts,
            "jobs": sum(s["fetched"] for s in sources),
            "sources_ok": sum(s["state"] == "ok" for s in sources),
            "shortlist": _number(r.get("jobs", {}).get("shortlist") and
                                 len(r["jobs"]["shortlist"])),
        })
    return list(reversed(points))

def build_public_payload(root: Path) -> dict:
    report = _load(root / "latest.json")
    status = _load(root / "status.json")
    sources = _sources(report)
    upwork = _upwork_verification(root)
    scanned = sum(row["fetched"] for row in sources)
    ok = sum(row["state"] == "ok" for row in sources)
    candidates = report.get("jobs", {}).get("shortlist") or []
    mcp = report.get("mcp_catalog", {})
    apify = report.get("apify_catalog", {})
    when = _safe_iso(report.get("run_at")) or _safe_iso(status.get("last_run"))
    now = datetime.now(timezone.utc)
    age = (now - datetime.fromisoformat(when)).total_seconds() if when else float("inf")
    healthy = status.get("status") == "success" and age < 8 * 3600 and ok >= 4
    degraded = status.get("status") == "success" and 0 <= age < 12 * 3600
    state = "running" if healthy else ("degraded" if degraded else "offline")
    stages = [
        {"id": "api", "name": "公式データの取得", "done": ok >= 4,
         "detail": f"{ok}/{len(SOURCES)} 媒体の取得が成功"},
        {"id": "schedule", "name": "PCバックグラウンド運転", "done": healthy,
         "detail": "6時間間隔の自律収集（PC稼働が前提）"},
        {"id": "qualify", "name": "案件の採点・候補化", "done": isinstance(candidates, list) and
         "shortlist" in report.get("jobs", {}),
         "detail": "フィルタリングと提案案の作成"},
        {"id": "mcp", "name": "新規MCP・APIの探索", "done": mcp.get("status", {}).get("state") ==
         "read_only_success" and apify.get("status", {}).get("state") == "read_only_success",
         "detail": "自動発見のみ、権限の自動付与なし"},
        {"id": "apply", "name": "許諾済み案件への応募",
         "done": upwork["verification"] == "recent" and
                 bool(upwork["submitted"] and upwork["submitted"] > 0),
         "detail": "公式MCPの提出済記録を反映（未確認時は未達扱い）"},
        {"id": "contract", "name": "受注・外注手配", "done": False,
         "detail": "正式契約・再委託同意が未達"},
        {"id": "payment", "name": "検収・初回入金", "done": False,
         "detail": "銀行/プラットフォーム上の入金照合未実施"},
    ]
    return {
        "schema": 1, "published_at": now.isoformat(), "last_run": when,
        "next_run_estimate": (datetime.fromisoformat(when) + timedelta(hours=6)).isoformat()
                              if when else None,
        "health": state,
        "metrics": {"sources_ok": ok, "sources_total": len(SOURCES),
                    "jobs_fetched": scanned,
                    "candidates": len(candidates) if isinstance(candidates, list) else 0,
                    "mcp_found": _number(mcp.get("status", {}).get("count")),
                    "mcp_indexed": min(len(mcp.get("candidates", [])), 60),
                    "apify_found": _number(apify.get("status", {}).get("count")),
                    "applications": upwork["submitted"], "contracts": 0, "outsourced": 0,
                    "revenue_jpy_verified": 0},
        "sources": sources, "upwork": upwork,
        "stages": stages, "history": _run_series(root),
        "operation": {
            "collection_interval_hours": 6,
            "public_report_only": True,
            "github_ci": "blocked_billing",
            "mcp_auth": "no_unreviewed_install",
            "publication": "Cloudflare Pages",
            "background": "Windows Task Scheduler / pythonw",
        }
    }

def export(root: Path, site_dir: Path) -> dict:
    site_dir.mkdir(parents=True, exist_ok=True)
    for name in PUBLIC_FILES:
        shutil.copyfile(SITE_SOURCE / name, site_dir / name)
    data = build_public_payload(root)
    (site_dir / "status.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    names = sorted(p.name for p in site_dir.iterdir() if p.is_file())
    assert names == sorted(list(PUBLIC_FILES) + ["status.json"]), (
        "Unexpected file in public directory — refuse to upload!")
    assert "external_id" not in (site_dir / "status.json").read_text(encoding="utf-8")
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--site-dir", default=None)
    ap.add_argument("--deploy", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    output = Path(args.site_dir) if args.site_dir else root / "public-site"
    info = export(root, output)
    summary = {"state": "exported", "sources": info["metrics"]["sources_ok"],
               "fetched": info["metrics"]["jobs_fetched"],
               "progress": sum(s["done"] for s in info["stages"])}
    if args.deploy:
        command = shutil.which("wrangler.cmd") or shutil.which("wrangler")
        if not command:
            summary["deployment"] = "blocked_wrangler_not_found"
        else:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                proc = subprocess.run(
                    [command, "pages", "deploy", str(output), "--project-name",
                     PROJECT, "--branch", "main"],
                    capture_output=True, text=True, timeout=135,
                    creationflags=flags, stdin=subprocess.DEVNULL,
                    env={**os.environ, "WRANGLER_SEND_METRICS": "false"})
                summary["deployment"] = "success" if proc.returncode == 0 else "failed"
                summary["exit_code"] = proc.returncode
                # NEVER echo full command stdout/stderr (may contain private metadata).
            except (subprocess.SubprocessError, OSError):
                summary["deployment"] = "failed"
        (root / "publish-status.json").write_text(
            json.dumps({**summary, "attempted_at": datetime.now(timezone.utc).isoformat()},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == "__main__":
    main()
