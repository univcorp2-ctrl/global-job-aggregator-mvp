"""Autonomous, permission-aware earnings scout across multiple marketplaces.

Runs unattended for read-only discovery, scoring, proposal drafts and audit artifacts.
NO platform logins, application submission, subcontract orders, or payment actions.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core import Settings, collect_all, connect, init_db, list_jobs

MCP_REGISTRY = "https://registry.modelcontextprotocol.io/v0.1/servers"
APIFY_STORE = "https://api.apify.com/v2/store"
SEARCH_TERMS = ("marketplace", "freelance", "commerce", "automation", "booking")
APIFY_TERMS = ("data extraction", "lead generation", "api")
LIMIT = 150
MAX_DRAFTS = 15
# Search does not prove job/subcontract eligibility. No automatic outbound actions.
REQUIRES_REVIEW = (
    "Verify listing is open and source is licensed for reuse.",
    "Verify fixed-price vs employment and eligibility to work from Japan.",
    "Confirm customer specification, fulfillment capacity and work ownership.",
    "Confirm client consent to subcontract and applicable marketplace rules.",
    "Confirm payment terms before issuing a worker purchase order.",
    "Approve proposal wording, any application fee, and the platform's write step.",
)

CAPABILITY_MANIFEST = {
    "upwork": {"mode": "official_mcp", "connection": "external_oauth_session_only",
               "read": ["jobs", "worker_search"], "write": "platform_confirmation_required",
               "background_api_credentials": "not_configured", "automated_bids": False},
    "freelancer": {"mode": "official_oauth_api",
                   "connection": "requires_FREELANCER_OAUTH_TOKEN",
                   "read": ["projects", "worker_directory"],
                   "write": "requires_permission_and_confirmation",
                   "automated_bids": False},
    "contra": {"mode": "official_mcp", "connection": "external_oauth_session_only",
               "read": ["opportunities", "talent"], "write": "platform_confirmation_required",
               "automated_bids": False},
    "apify": {"mode": "official_store_api", "connection": "public_store_read_only",
              "read": ["store_listing"], "write": "publication_needs_KYC_and_approval",
              "automated_bids": False},
    "mcp_registry": {"mode": "official_registry_rest",
                     "connection": "public_catalog", "read": ["registered_metadata"],
                     "write": "requires_authentication_and_manual_security_review",
                     "automated_bids": False},
    "public_jobs": {"mode": "existing_official_public_apis",
                    "connection": "no_credentials_for_5_feeds",
                    "read": ["job_metadata"], "write": "source_specific_apply",
                    "automated_bids": False},
}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_url(url: Any) -> str | None:
    if not isinstance(url, str) or len(url) > 1024:
        return None
    p = urlparse(url)
    return url if p.scheme == "https" and p.hostname else None

def _short(text: Any, limit: int = 250) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]

def _items(payload: Any) -> list[dict[str, Any]]:
    """Extract safe listing arrays without assuming one vendor response shape."""
    if not isinstance(payload, dict):
        return []
    options = [payload.get("servers"), payload.get("items"),
               payload.get("results"), payload.get("data")]
    if isinstance(payload.get("data"), dict):
        options += [payload["data"].get("items"), payload["data"].get("results")]
    for val in options:
        if isinstance(val, list):
            return [v for v in val if isinstance(v, dict)]
    return []

def _status(mode: str, count: int = 0, error: str | None = None) -> dict[str, Any]:
    return {"state": "read_only_success" if error is None else "unavailable",
            "mode": mode, "count": count, "error": _short(error, 160) if error else None}

async def catalog_mcp(client: httpx.AsyncClient, *, terms: tuple[str, ...] = SEARCH_TERMS
                      ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Official registry, no auto-install: metadata is untrusted until security review."""
    found: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for term in terms[:6]:
        try:
            response = await client.get(MCP_REGISTRY,
                                        params={"search": term, "limit": 20, "version": "latest"})
            response.raise_for_status()
            for record in _items(response.json()):
                server = record.get("server", record)
                if not isinstance(server, dict):
                    continue
                name = _short(server.get("name"), 180)
                if not name:
                    continue
                title = _short(server.get("title") or name)
                found[name] = {
                    "name": name, "title": title, "search_term": term,
                    "description": _short(server.get("description"), 300),
                    "verified": False, "automatically_installed": False,
                    "next_gate": "review_publisher_permissions_and_security",
                }
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{term}: {type(exc).__name__}")
    status = _status("official_registry_v0.1", len(found),
                     ", ".join(errors) if errors and not found else None)
    status["partial_errors"] = errors
    return list(found.values())[:60], status

async def catalog_apify(client: httpx.AsyncClient,
                        *, terms: tuple[str, ...] = APIFY_TERMS
                        ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover competing Actors and buyer demand signals; never claim actual sales."""
    found: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for term in terms[:4]:
        try:
            r = await client.get(APIFY_STORE, params={"search": term, "limit": 20})
            r.raise_for_status()
            for item in _items(r.json()):
                ident = _short(item.get("id") or item.get("name"), 110)
                if not ident:
                    continue
                found[ident] = {
                    "id": ident, "title": _short(item.get("title") or item.get("name")),
                    "search_term": term, "url": _safe_url(item.get("url")),
                    "description": _short(item.get("description"), 300),
                    "potential_product_signal": True,
                    "verified_customer_purchase": False,
                }
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{term}: {type(exc).__name__}")
    status = _status("apify_official_store", len(found),
                     ", ".join(errors) if errors and not found else None)
    status["partial_errors"] = errors
    return list(found.values())[:60], status

def _is_employment(row: dict[str, Any]) -> bool:
    text = " ".join([_short(row.get("title")), _short(row.get("contract_type")),
                     _short(row.get("description"), 400)]).lower()
    return bool(re.search(r"\b(full.time employee|permanent employment|w.?2|salary|annual salary)\b", text))

def _is_probable_project(row: dict[str, Any]) -> bool:
    text = " ".join([_short(row.get("title")), _short(row.get("contract_type")),
                     _short(row.get("description"), 500)]).lower()
    return bool(re.search(r"\b(freelanc\w*|contractor|fixed.price|project.based|paid pilot|consulting project)\b", text))

def _feedback_multiplier(row: dict[str, Any], feedback: dict[str, Any]) -> float:
    """Auditable, bounded adjustment: no invented wins and no self-modifying code."""
    source = str(row.get("source") or "")
    stats = feedback.get(source, {})
    if not isinstance(stats, dict):
        return 1.0
    submitted, won = stats.get("submitted", 0), stats.get("won", 0)
    if (not isinstance(submitted, int) or not isinstance(won, int) or
        isinstance(submitted, bool) or isinstance(won, bool) or
        not 0 <= won <= submitted <= 10000):
        return 1.0
    if submitted < 5:
        return 1.0
    # Laplace-smoothed conversion and a conservative +/- 15% clamp.
    conversion = (won + 1) / (submitted + 2)
    return round(max(.85, min(1.15, 1 + (conversion - .12) * .30)), 3)

def score_candidate(row: dict[str, Any], feedback: dict[str, Any] | None = None
                    ) -> dict[str, Any]:
    feedback = feedback or {}
    employment = _is_employment(row)
    project = _is_probable_project(row)
    ai = max(0., min(100., float(row.get("ai_relevance") or 0)))
    fit = max(0., min(100., float(row.get("fit_score") or 0)))
    has_url = bool(_safe_url(row.get("url")))
    base = (.48 * ai + .32 * fit + (10 if project else 0)
            + (5 if has_url else -15) - (40 if employment else 0))
    score = round(max(0, min(100, base * _feedback_multiplier(row, feedback))), 1)
    gates = list(REQUIRES_REVIEW)
    if employment:
        label = "employment_not_subcontractable_without_new_contract"
    elif project:
        label = "possible_paid_project_unverified"
    else:
        label = "job_type_unclear"
    return {
        "source": _short(row.get("source"), 60),
        "external_id": _short(row.get("external_id"), 120),
        "title": _short(row.get("title"), 180),
        "url": _safe_url(row.get("url")),
        "score": score, "opportunity_type": label,
        "compensation_as_advertised": _short(row.get("compensation"), 100) or None,
        "is_confirmed_contract": False,
        "expected_net_profit": None,  # Never invent outsourcing costs.
        "draft_only": _short(row.get("proposal_draft"), 900) or None,
        "review_gates": gates,
        "next_action": "manual_qualification_then_provider_native_approval",
    }

def _load_feedback(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}

def evaluate_database(path: Path, feedback: dict[str, Any],
                      limit: int = LIMIT) -> dict[str, Any]:
    init_db(path)
    with connect(path) as conn:
        raw = list_jobs(conn, limit=limit)
        counts = {row["source"]: row["count"] for row in
                  conn.execute("SELECT source, COUNT(*) AS count FROM jobs GROUP BY source")}
    scored = [score_candidate(r, feedback) for r in raw]
    shortlist = sorted(
        (x for x in scored if x["opportunity_type"] == "possible_paid_project_unverified"
         and x["url"]), key=lambda x: x["score"], reverse=True
    )[:MAX_DRAFTS]
    return {"fetched_rows_evaluated": len(raw), "source_counts": counts,
            "possible_project_candidates": len([x for x in scored if
                                                  x["opportunity_type"] ==
                                                  "possible_paid_project_unverified"]),
            "shortlist": shortlist, "queued_for_automatic_submission": 0}

async def run_once(db_path: Path, *, perform_collection: bool,
                   feedback_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_at": utcnow(), "version": "0.1.0", "execution": "scheduled_read_only",
        "platforms": CAPABILITY_MANIFEST,
        "external_calls": {"submissions": 0, "offers": 0, "contracts": 0,
                           "subcontracts": 0, "payments": 0},
        "warnings": ["Published listings and MCP metadata are not verified sales.",
                     "Official MCP registry entries are NEVER auto-installed."],
    }
    if perform_collection:
        try:
            settings = Settings.from_env()
            # Override only local DB path; preserve all defaults for existing public sources.
            from dataclasses import replace
            summary = await collect_all(settings=replace(settings, db_path=db_path), force=True)
            result["collect"] = summary.as_dict()
        except Exception as exc:
            result["collect_error"] = f"{type(exc).__name__}: {_short(exc, 160)}"
    result["jobs"] = evaluate_database(db_path, _load_feedback(feedback_path))
    async with httpx.AsyncClient(timeout=12, follow_redirects=False,
                                 headers={"User-Agent": "GlobalRevenueAgent/0.1"}) as client:
        mcp, mcp_state = await catalog_mcp(client)
        actors, apify_state = await catalog_apify(client)
    result["mcp_catalog"] = {"status": mcp_state, "candidates": mcp}
    result["apify_catalog"] = {"status": apify_state, "candidates": actors}
    result["audit"] = {
        "auto_sign_up": False, "auto_install_mcp": False, "auto_apply": False,
        "auto_message": False, "auto_hire": False, "auto_payment": False,
        "user_review_required_for_external_writes": True,
        "revenue_confirmed": 0,
    }
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Safe autonomous multi-market earnings scout")
    parser.add_argument("--db", default=os.getenv("DB_PATH", "data/jobs.db"))
    parser.add_argument("--output", default="data/agent-report.json")
    parser.add_argument("--feedback", default="data/agent-feedback.json")
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_once(Path(args.db), perform_collection=args.collect,
                                  feedback_path=Path(args.feedback)))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report_path": str(target),
        "sources": result["jobs"]["source_counts"],
        "shortlist": len(result["jobs"]["shortlist"]),
        "mcp_candidates": len(result["mcp_catalog"]["candidates"]),
        "apify_candidates": len(result["apify_catalog"]["candidates"]),
        "outbound_writes": sum(result["external_calls"].values()),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
