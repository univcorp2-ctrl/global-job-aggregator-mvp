"""Consent-aware worker supply registry and read-only matching.

This database is private, separate from the public job index. Never bulk-import
personal profiles or expose direct contact details. Platform contact is gated.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

PROVIDERS = {
    "contra": {
        "region": "global", "discovery": "official_mcp_oauth",
        "contact": "prepare_confirm_only", "connected": False,
        "docs": "https://contra.com/features/mcp",
    },
    "freelancer": {
        "region": "global", "discovery": "official_api_oauth",
        "contact": "project_thread_and_permissions", "connected": False,
        "docs": "https://github.com/freelancer/freelancer-sdk-python",
    },
    "coconala": {
        "region": "japan", "discovery": "official_mcp_service_search",
        "contact": "on_platform_only", "connected": False,
        "docs": "https://mcp.ai-assist.coconala.com/legal/mcp_terms",
    },
    "crowdworks": {
        "region": "japan", "discovery": "no_verified_public_worker_api",
        "contact": "on_platform_only", "connected": False,
        "docs": "https://crowdworks.jp/pages/agreement",
    },
    "lancers": {
        "region": "japan", "discovery": "no_verified_public_worker_api",
        "contact": "on_platform_only", "connected": False,
        "docs": "https://www.lancers.jp/",
    },
    "getonboard": {
        "region": "latin_america", "discovery": "company_scoped_mcp_oauth",
        "contact": "company_authorization_required", "connected": False,
        "docs": "https://www.getonbrd.com/help/what-is-the-getonbrd-mcp-server",
    },
    "wantedly_hire": {
        "region": "japan", "discovery": "employer_ats_read_only_mcp",
        "contact": "no_mcp_write", "connected": False,
        "docs": "https://hire.wantedly.com/mcp",
    },
    "opt_in": {
        "region": "global", "discovery": "worker_submitted_consent",
        "contact": "explicit_consent_and_human_review", "connected": True,
        "docs": "",
    },
}

DDL = """
CREATE TABLE IF NOT EXISTS workers (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  platform_worker_id TEXT NOT NULL,
  display_label TEXT NOT NULL,
  profile_url TEXT,
  skills_json TEXT NOT NULL,
  languages_json TEXT NOT NULL DEFAULT '[]',
  location TEXT,
  remote_ok INTEGER NOT NULL DEFAULT 0,
  hourly_rate REAL,
  currency TEXT,
  availability TEXT NOT NULL DEFAULT 'unknown',
  consent_basis TEXT NOT NULL,
  profile_origin TEXT NOT NULL,
  permitted_contact TEXT NOT NULL DEFAULT 'platform_only',
  checked_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(platform, platform_worker_id)
);
CREATE INDEX IF NOT EXISTS idx_workers_platform ON workers(platform);
CREATE TABLE IF NOT EXISTS contact_drafts (
  id TEXT PRIMARY KEY,
  job_id INTEGER NOT NULL,
  worker_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  draft_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'prepared_not_sent',
  created_at TEXT NOT NULL
);
"""

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class WorkerConnection(sqlite3.Connection):
    """Ensure Windows releases SQLite handles after a with-statement."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def connect_workers(path: str | Path) -> sqlite3.Connection:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(dest), factory=WorkerConnection)
    db.row_factory = sqlite3.Row
    db.executescript(DDL)
    return db

def _verify_profile_url(platform: str, value: str | None) -> str | None:
    if not value:
        return None
    u = urlparse(value)
    allowed = {
        "contra": ("contra.com",),
        "freelancer": ("freelancer.com",),
        "coconala": ("coconala.com",),
        "crowdworks": ("crowdworks.jp",),
        "lancers": ("lancers.jp",),
        "getonboard": ("getonbrd.com",),
        "wantedly_hire": ("wantedly.com",),
        "opt_in": (),
    }
    hosts = allowed.get(platform)
    if hosts is None or u.scheme != "https" or not u.hostname:
        raise ValueError("A verified HTTPS worker profile URL is required")
    if hosts and not any(u.hostname == h or u.hostname.endswith("." + h) for h in hosts):
        raise ValueError("Profile URL must be on its own platform")
    return value

def register_worker(
    db: sqlite3.Connection, *,
    platform: str, external_id: str, display_label: str,
    skills: list[str], profile_url: str | None = None,
    languages: list[str] | None = None, location: str | None = None,
    remote_ok: bool = False, hourly_rate: float | None = None,
    currency: str | None = None, availability: str = "unknown",
    consent_basis: str = "opt_in", profile_origin: str = "worker_submission",
) -> str:
    if platform not in PROVIDERS:
        raise ValueError("Unknown platform")
    if consent_basis not in {"opt_in", "platform_authorized"}:
        raise ValueError("No lawful consent/authorization basis")
    if consent_basis == "platform_authorized" and profile_origin != "authorized_official_api":
        raise ValueError("External candidate import requires a verified official API")
    if platform != "opt_in" and consent_basis == "opt_in" and profile_origin != "worker_submission":
        raise ValueError("Self-submitted consent must originate with the worker")
    if not external_id.strip() or not display_label.strip():
        raise ValueError("Missing worker identifier or label")
    if len(external_id) > 130 or len(display_label) > 120 or len(skills) > 30:
        raise ValueError("Oversized worker profile")
    if hourly_rate is not None and not (0 <= hourly_rate <= 1_000_000):
        raise ValueError("Invalid quoted rate")
    if currency is not None and (len(currency) != 3 or not currency.isalpha()):
        raise ValueError("Currency must be an ISO-style three-letter code")
    clean_skills = list(dict.fromkeys(s.strip().lower() for s in skills if isinstance(s, str) and s.strip()))
    if not clean_skills:
        raise ValueError("Skills required")
    url = _verify_profile_url(platform, profile_url)
    uid = hashlib.sha256(f"{platform}:{external_id}".encode()).hexdigest()[:28]
    now = utc_now()
    expiry = now + timedelta(days=30 if consent_basis == "platform_authorized" else 365)
    # No emails, phones, message contents or protected attributes are stored.
    db.execute("""INSERT INTO workers (
      id,platform,platform_worker_id,display_label,profile_url,skills_json,languages_json,
      location,remote_ok,hourly_rate,currency,availability,consent_basis,profile_origin,
      permitted_contact,checked_at,expires_at,updated_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(id) DO UPDATE SET
      display_label=excluded.display_label,profile_url=excluded.profile_url,
      skills_json=excluded.skills_json,languages_json=excluded.languages_json,
      location=excluded.location,remote_ok=excluded.remote_ok,
      hourly_rate=excluded.hourly_rate,currency=excluded.currency,
      availability=excluded.availability,checked_at=excluded.checked_at,
      expires_at=excluded.expires_at,updated_at=excluded.updated_at
    """, (uid,platform,external_id,display_label,url,json.dumps(clean_skills),
      json.dumps((languages or [])[:20]),location,int(remote_ok),hourly_rate,
      currency.upper() if currency else None,availability,consent_basis,profile_origin,
      "platform_only",now.isoformat(),expiry.isoformat(),now.isoformat()))
    db.commit()
    return uid

def search_workers(db: sqlite3.Connection, *, skill: str = "", platform: str = "", limit: int = 50) -> list[dict]:
    now = utc_now().isoformat()
    query = "SELECT * FROM workers WHERE expires_at > ?"
    params: list = [now]
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if skill:
        query += " AND skills_json LIKE ?"
        params.append("%" + skill.lower().replace("%", "").replace("_", "") + "%")
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(100,limit)))
    out = []
    for r in db.execute(query, params).fetchall():
        item = dict(r)
        item["skills"] = json.loads(item.pop("skills_json"))
        item["languages"] = json.loads(item.pop("languages_json"))
        item.pop("platform_worker_id", None)
        out.append(item)
    return out

def match_workers(db: sqlite3.Connection, job: dict, limit: int = 10) -> list[dict]:
    from app.core import detect_skills
    source_text = " ".join(str(job.get(k) or "") for k in ("title","description","required_skills"))
    wanted = {s.lower() for s in detect_skills(source_text)}
    if isinstance(job.get("required_skills"), list):
        wanted |= {s.lower() for s in job["required_skills"]}
    elif isinstance(job.get("required_skills"), str):
        try:
            wanted |= {str(s).lower() for s in json.loads(job["required_skills"])}
        except (ValueError, TypeError):
            pass
    output = []
    for person in search_workers(db, limit=100):
        skills = set(person["skills"])
        matches = sorted(s for s in skills if s in wanted or any(s in w or w in s for w in wanted))
        if not matches:
            continue
        score = min(100, 20 + 15 * len(matches) + (10 if person.get("remote_ok") else 0))
        output.append({
            "worker_id": person["id"], "platform": person["platform"],
            "display_label": person["display_label"],"profile_url": person["profile_url"],
            "skills_matched": matches, "score":score,
            "hourly_rate":person["hourly_rate"], "currency":person["currency"],
            "status":"candidate_only_subcontract_permission_unverified",
        })
    return sorted(output,key=lambda x:x["score"],reverse=True)[:min(50,max(1,limit))]

def prepare_contact(db: sqlite3.Connection, *, job: dict, worker_id: str) -> dict:
    worker = db.execute("SELECT * FROM workers WHERE id=? AND expires_at>?",
       (worker_id,utc_now().isoformat())).fetchone()
    if worker is None:
        raise ValueError("Worker unavailable or outdated")
    text = (
      f"Hello, I am reviewing a potential {job.get('title','project')} collaboration. "
      "Could you share your availability, estimated rate and relevant portfolio? "
      "The project scope, subcontract permissions and confidential information "
      "would be confirmed before any commitment."
    )
    key = hashlib.sha256(f"{job.get('id')}:{worker_id}".encode()).hexdigest()[:28]
    db.execute("INSERT OR IGNORE INTO contact_drafts(id,job_id,worker_id,platform,draft_text,created_at) "
               "VALUES (?,?,?,?,?,?)",
               (key,int(job['id']),worker_id,worker['platform'],text,utc_now().isoformat()))
    db.commit()
    return {
        "draft_id":key,"message":text,"platform":worker["platform"],
        "profile_url":worker["profile_url"],"state":"prepared_not_sent",
        "send_enabled":False,"needs_platform_permission":True,
        "needs_human_confirmation":True,
        "requires_verified_subcontract_rights":True,
    }

def provider_capabilities() -> dict:
    # Connection status intentionally reflects this application's real session.
    return PROVIDERS
