from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import httpx

DEFAULT_KEYWORDS = [
    "AI Agent Developer",
    "RAG",
    "Vector Database",
    "LangChain",
    "LlamaIndex",
    "OpenAI API",
    "Claude API",
    "Gemini API Integration",
    "Workflow Automation",
    "Zapier",
    "Make",
    "n8n",
    "Web Scraping AI Analysis",
    "LLM Evaluator",
    "Code Evaluator",
    "AI Real Estate",
    "PropTech Automation",
]

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
HOURLY_RE = re.compile(r"(?:\$|USD\s*)?(\d{2,4})(?:\.\d+)?\s*(?:/|per)?\s*(?:hour|hr)", re.I)
ANNUAL_RE = re.compile(r"(?:\$|USD\s*)?(\d{2,3})(?:,?\d{3}|k)\b", re.I)
SKILL_PATTERNS: dict[str, int] = {
    "AI Agent": 10,
    "RAG": 9,
    "Vector Database": 8,
    "LangChain": 8,
    "LlamaIndex": 8,
    "OpenAI API": 9,
    "Claude API": 8,
    "Gemini API": 7,
    "LLM": 7,
    "Workflow Automation": 8,
    "Zapier": 6,
    "Make": 5,
    "n8n": 6,
    "Python": 6,
    "FastAPI": 5,
    "Web Scraping": 7,
    "Google Sheets": 6,
    "Data Extraction": 6,
    "Evaluation": 5,
    "Code Review": 5,
    "Real Estate": 7,
    "PropTech": 7,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    url TEXT,
    location TEXT,
    compensation TEXT,
    contract_type TEXT,
    remote TEXT,
    japan_ok TEXT,
    required_skills TEXT NOT NULL DEFAULT '[]',
    ai_relevance REAL NOT NULL DEFAULT 0,
    fit_score REAL NOT NULL DEFAULT 0,
    expected_monthly_income TEXT,
    application_priority TEXT NOT NULL DEFAULT 'C',
    proposal_draft TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    description TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(application_priority, ai_relevance);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE TABLE IF NOT EXISTS source_runs (
    source TEXT PRIMARY KEY,
    last_attempt_at TEXT,
    last_success_at TEXT,
    last_status TEXT,
    last_error TEXT,
    last_count INTEGER NOT NULL DEFAULT 0
);
"""

JOB_COLUMNS = [
    "source",
    "external_id",
    "title",
    "company",
    "url",
    "location",
    "compensation",
    "contract_type",
    "remote",
    "japan_ok",
    "required_skills",
    "ai_relevance",
    "fit_score",
    "expected_monthly_income",
    "application_priority",
    "proposal_draft",
    "status",
    "description",
    "published_at",
    "fetched_at",
    "raw_json",
    "updated_at",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/jobs.db")
    keywords: list[str] = field(default_factory=lambda: DEFAULT_KEYWORDS.copy())
    max_per_source: int = 50
    request_delay_seconds: float = 0.7
    http_timeout_seconds: float = 20.0
    contact_email: str = "you@example.com"
    greenhouse_boards: list[str] = field(default_factory=list)
    lever_companies: list[str] = field(default_factory=list)
    ashby_boards: list[str] = field(default_factory=list)
    serpapi_api_key: str | None = None
    freelancer_oauth_token: str | None = None
    cooldown_hours: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_path=Path(os.getenv("DB_PATH", "data/jobs.db")),
            keywords=parse_csv(os.getenv("JOB_KEYWORDS")) or DEFAULT_KEYWORDS.copy(),
            max_per_source=env_int("MAX_PER_SOURCE", 50),
            request_delay_seconds=env_float("REQUEST_DELAY_SECONDS", 0.7),
            http_timeout_seconds=env_float("HTTP_TIMEOUT_SECONDS", 20.0),
            contact_email=os.getenv("CONTACT_EMAIL", "you@example.com"),
            greenhouse_boards=parse_csv(os.getenv("GREENHOUSE_BOARDS")),
            lever_companies=parse_csv(os.getenv("LEVER_COMPANIES")),
            ashby_boards=parse_csv(os.getenv("ASHBY_BOARDS")),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY") or None,
            freelancer_oauth_token=os.getenv("FREELANCER_OAUTH_TOKEN") or None,
            cooldown_hours={
                "himalayas": env_float("HIMALAYAS_COOLDOWN_HOURS", 1),
                "jobicy": env_float("JOBICY_COOLDOWN_HOURS", 1),
                "arbeitnow": env_float("ARBEITNOW_COOLDOWN_HOURS", 1),
                "remotive": env_float("REMOTIVE_COOLDOWN_HOURS", 6),
                "greenhouse": env_float("ATS_COOLDOWN_HOURS", 6),
                "lever": env_float("ATS_COOLDOWN_HOURS", 6),
                "ashby": env_float("ATS_COOLDOWN_HOURS", 6),
                "serpapi": env_float("SERPAPI_COOLDOWN_HOURS", 6),
                "freelancer": env_float("FREELANCER_COOLDOWN_HOURS", 6),
            },
        )

    @property
    def user_agent(self) -> str:
        return f"GlobalJobAggregatorMVP/0.1 (+mailto:{self.contact_email})"


@dataclass(slots=True)
class NormalizedJob:
    source: str
    external_id: str
    title: str
    company: str | None = None
    url: str | None = None
    location: str | None = None
    compensation: str | None = None
    contract_type: str | None = None
    remote: str | None = None
    japan_ok: str | None = None
    required_skills: list[str] = field(default_factory=list)
    ai_relevance: float = 0.0
    fit_score: float = 0.0
    expected_monthly_income: str | None = None
    application_priority: str = "C"
    proposal_draft: str | None = None
    status: str = "new"
    description: str | None = None
    published_at: str | None = None
    fetched_at: str = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "external_id": str(self.external_id),
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "location": self.location,
            "compensation": self.compensation,
            "contract_type": self.contract_type,
            "remote": self.remote,
            "japan_ok": self.japan_ok,
            "required_skills": json.dumps(self.required_skills, ensure_ascii=False),
            "ai_relevance": self.ai_relevance,
            "fit_score": self.fit_score,
            "expected_monthly_income": self.expected_monthly_income,
            "application_priority": self.application_priority,
            "proposal_draft": self.proposal_draft,
            "status": self.status,
            "description": self.description,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
            "raw_json": json.dumps(self.raw, ensure_ascii=False),
            "updated_at": utc_now(),
        }


def compact(value: str | None) -> str | None:
    if value is None:
        return None
    return SPACE_RE.sub(" ", str(value)).strip()


def strip_html(value: str | None) -> str | None:
    if not value:
        return value
    text = TAG_RE.sub(" ", value)
    return compact(html.unescape(text))


def join_values(values: Iterable[Any] | None, sep: str = ", ") -> str | None:
    if not values:
        return None
    cleaned = [compact(str(v)) for v in values if compact(str(v))]
    return sep.join(cleaned) if cleaned else None


def safe_get(mapping: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def detect_skills(text: str) -> list[str]:
    lowered = text.lower()
    return [skill for skill in SKILL_PATTERNS if skill.lower() in lowered]


def score_text(text: str) -> float:
    lowered = text.lower()
    score = sum(weight for skill, weight in SKILL_PATTERNS.items() if skill.lower() in lowered)
    if any(pattern in lowered for pattern in ["unpaid", "volunteer", "commission only"]):
        score -= 10
    return max(0.0, min(100.0, float(score)))


def estimate_monthly_income(compensation: str | None) -> str | None:
    if not compensation:
        return None
    text = compensation.replace(",", "")
    hourly = [int(match) for match in HOURLY_RE.findall(text)]
    if hourly:
        monthly = (sum(hourly) / len(hourly)) * 120
        return f"USD {monthly:,.0f}/mo estimate at 120h"
    annual: list[int] = []
    for match in ANNUAL_RE.findall(text):
        number = int(match)
        annual.append(number * 1000 if number < 1000 else number)
    if annual:
        monthly = (sum(annual) / len(annual)) / 12
        return f"USD {monthly:,.0f}/mo estimate from annual range"
    return None


def build_proposal(job: NormalizedJob) -> str:
    skills = ", ".join(job.required_skills[:5]) or "AI automation and data workflows"
    company = f" at {job.company}" if job.company else ""
    return (
        f"Hi, I found your {job.title}{company} opportunity and it looks aligned with my work in "
        f"{skills}. I can help turn fragmented web/API data into reliable automations, dashboards, "
        "and business-ready reports using Python, APIs, AI tools, and spreadsheet/database workflows. "
        "I would start by clarifying the target outcome, building a small reliable pipeline, then adding "
        "monitoring and a clean handoff so the system stays maintainable."
    )


def enrich_job(job: NormalizedJob) -> NormalizedJob:
    text = strip_html(" ".join(str(v) for v in [job.title, job.company, job.description, job.contract_type, job.compensation] if v)) or ""
    skills = detect_skills(text)
    job.required_skills = list(dict.fromkeys(job.required_skills + skills))
    job.ai_relevance = score_text(text)
    job.fit_score = min(100.0, job.ai_relevance + (15 if "Real Estate" in job.required_skills else 0))
    job.expected_monthly_income = job.expected_monthly_income or estimate_monthly_income(job.compensation)
    total = job.ai_relevance + job.fit_score + (10 if job.compensation and ("$" in job.compensation or "USD" in job.compensation.upper()) else 0)
    job.application_priority = "A" if total >= 85 else "B" if total >= 55 else "C"
    job.proposal_draft = job.proposal_draft or build_proposal(job)
    return job


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_job(conn: sqlite3.Connection, job: NormalizedJob) -> bool:
    before = conn.total_changes
    record = job.to_record()
    placeholders = ", ".join(f":{col}" for col in JOB_COLUMNS)
    columns = ", ".join(JOB_COLUMNS)
    updates = ", ".join(f"{col}=excluded.{col}" for col in JOB_COLUMNS if col not in {"source", "external_id", "status"})
    sql = f"""
    INSERT INTO jobs ({columns}) VALUES ({placeholders})
    ON CONFLICT(source, external_id) DO UPDATE SET {updates}, status=jobs.status
    """
    conn.execute(sql, record)
    conn.commit()
    return conn.total_changes > before


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["required_skills"] = json.loads(item.get("required_skills") or "[]")
    except json.JSONDecodeError:
        item["required_skills"] = []
    try:
        item["raw"] = json.loads(item.get("raw_json") or "{}")
    except json.JSONDecodeError:
        item["raw"] = {}
    return item


def list_jobs(conn: sqlite3.Connection, *, q: str | None = None, source: str | None = None, status: str | None = None, priority: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": max(1, min(limit, 500))}
    if q:
        params["q"] = f"%{q.lower()}%"
        conditions.append("(lower(title) LIKE :q OR lower(company) LIKE :q OR lower(description) LIKE :q OR lower(required_skills) LIKE :q)")
    if source:
        conditions.append("source = :source")
        params["source"] = source
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if priority:
        conditions.append("application_priority = :priority")
        params["priority"] = priority
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM jobs {where}
    ORDER BY CASE application_priority WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
             ai_relevance DESC,
             COALESCE(published_at, fetched_at) DESC
    LIMIT :limit
    """
    return [_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def source_counts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT source, COUNT(*) AS count FROM jobs GROUP BY source ORDER BY count DESC").fetchall()
    return [dict(row) for row in rows]


def record_source_run(conn: sqlite3.Connection, source: str, *, status: str, count: int, error: str | None = None) -> None:
    now = utc_now()
    success = now if status == "success" else None
    conn.execute(
        """
        INSERT INTO source_runs(source, last_attempt_at, last_success_at, last_status, last_error, last_count)
        VALUES(:source, :attempt, :success, :status, :error, :count)
        ON CONFLICT(source) DO UPDATE SET
            last_attempt_at=excluded.last_attempt_at,
            last_success_at=COALESCE(excluded.last_success_at, source_runs.last_success_at),
            last_status=excluded.last_status,
            last_error=excluded.last_error,
            last_count=excluded.last_count
        """,
        {"source": source, "attempt": now, "success": success, "status": status, "error": error, "count": count},
    )
    conn.commit()


def source_due(conn: sqlite3.Connection, source: str, cooldown_hours: float) -> bool:
    row = conn.execute("SELECT last_success_at FROM source_runs WHERE source = ?", (source,)).fetchone()
    if not row or not row["last_success_at"]:
        return True
    try:
        last_success = datetime.fromisoformat(row["last_success_at"])
    except ValueError:
        return True
    return datetime.now(UTC) - last_success >= timedelta(hours=cooldown_hours)


class Connector(ABC):
    name: str

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        raise NotImplementedError


async def request_json(client: httpx.AsyncClient, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, retries: int = 2) -> dict[str, Any]:
    for attempt in range(retries + 1):
        response = await client.get(url, params=params, headers=headers)
        if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
            await asyncio.sleep(2**attempt)
            continue
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"items": data}
    return {}


def default_headers(settings: Settings) -> dict[str, str]:
    return {"User-Agent": settings.user_agent, "Accept": "application/json"}


async def polite_sleep(settings: Settings) -> None:
    if settings.request_delay_seconds > 0:
        await asyncio.sleep(settings.request_delay_seconds)


class HimalayasConnector(Connector):
    name = "himalayas"
    endpoint = "https://himalayas.app/jobs/api/search"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords:
            data = await request_json(client, self.endpoint, params={"q": keyword, "sort": "recent", "page": 1}, headers=default_headers(settings))
            for item in data.get("jobs", []):
                locations = item.get("locationRestrictions") or []
                salary = salary_range(item.get("minSalary"), item.get("maxSalary"), item.get("currency") or "USD")
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("guid") or item.get("applicationLink") or item.get("title")), title=item.get("title") or "Untitled", company=item.get("companyName"), url=item.get("applicationLink"), location=join_values(locations) or "Worldwide", compensation=salary, contract_type=item.get("employmentType"), remote="remote", japan_ok="yes" if not locations or "japan" in ",".join(locations).lower() else "unknown", description=strip_html(item.get("description") or item.get("excerpt")), published_at=item.get("pubDate"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class JobicyConnector(Connector):
    name = "jobicy"
    endpoint = "https://jobicy.com/api/v2/remote-jobs"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords:
            data = await request_json(client, self.endpoint, params={"count": min(settings.max_per_source, 100), "tag": keyword}, headers=default_headers(settings))
            for item in data.get("jobs", []):
                geo = item.get("jobGeo") or "Anywhere"
                salary = salary_range(item.get("salaryMin"), item.get("salaryMax"), item.get("salaryCurrency") or "USD", item.get("salaryPeriod"))
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("id") or item.get("url") or item.get("jobTitle")), title=item.get("jobTitle") or "Untitled", company=item.get("companyName"), url=item.get("url"), location=geo, compensation=salary, contract_type=item.get("jobType"), remote="remote", japan_ok="yes" if str(geo).lower() in {"anywhere", "worldwide"} else "unknown", description=strip_html(item.get("jobDescription") or item.get("jobExcerpt")), published_at=item.get("pubDate"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class RemotiveConnector(Connector):
    name = "remotive"
    endpoint = "https://remotive.com/api/remote-jobs"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords[:3]:
            data = await request_json(client, self.endpoint, params={"search": keyword, "limit": min(settings.max_per_source, 25)}, headers=default_headers(settings))
            for item in data.get("jobs", []):
                location = item.get("candidate_required_location") or "Worldwide"
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("id") or item.get("url") or item.get("title")), title=item.get("title") or "Untitled", company=item.get("company_name"), url=item.get("url"), location=location, compensation=item.get("salary"), contract_type=item.get("job_type"), remote="remote", japan_ok="yes" if str(location).lower() in {"worldwide", "anywhere"} else "unknown", description=strip_html(item.get("description")), published_at=item.get("publication_date"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class ArbeitnowConnector(Connector):
    name = "arbeitnow"
    endpoint = "https://www.arbeitnow.com/api/job-board-api"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        data = await request_json(client, self.endpoint, headers=default_headers(settings))
        jobs: list[NormalizedJob] = []
        for item in data.get("data", data.get("items", [])):
            tags = item.get("tags") or []
            title = item.get("title") or "Untitled"
            description = strip_html(item.get("description"))
            searchable = f"{title} {description} {' '.join(tags)}".lower()
            if not any(keyword.lower() in searchable for keyword in settings.keywords):
                continue
            jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("slug") or item.get("url") or title), title=title, company=item.get("company_name"), url=item.get("url"), location=item.get("location"), contract_type=join_values(item.get("job_types") or []), remote="remote" if item.get("remote") else "unknown", japan_ok="unknown", required_skills=[str(tag) for tag in tags], description=description, published_at=str(item.get("created_at")) if item.get("created_at") else None, raw=item))
            if len(jobs) >= settings.max_per_source:
                return jobs
        return jobs


class GreenhouseConnector(Connector):
    name = "greenhouse"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for board in settings.greenhouse_boards:
            try:
                data = await request_json(client, f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"}, headers=default_headers(settings))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("jobs", []):
                location = (item.get("location") or {}).get("name")
                offices = [office.get("location") or office.get("name") for office in item.get("offices", [])]
                text = f"{location or ''} {' '.join(str(v) for v in offices)}".lower()
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("id") or item.get("absolute_url")), title=item.get("title") or "Untitled", company=board, url=item.get("absolute_url"), location=location or join_values(offices), contract_type=join_values([dept.get("name") for dept in item.get("departments", []) if dept.get("name")]), remote="remote" if "remote" in text else "unknown", japan_ok="yes" if any(token in text for token in ["remote", "worldwide", "japan"]) else "unknown", description=strip_html(item.get("content")), published_at=item.get("updated_at"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class LeverConnector(Connector):
    name = "lever"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for company in settings.lever_companies:
            try:
                data = await request_json(client, f"https://api.lever.co/v0/postings/{company}", params={"mode": "json"}, headers=default_headers(settings))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("items", []):
                location = safe_get(item, ["categories", "location"])
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("id") or item.get("hostedUrl") or item.get("text")), title=item.get("text") or "Untitled", company=company, url=item.get("hostedUrl") or item.get("applyUrl"), location=location, contract_type=safe_get(item, ["categories", "commitment"]) or safe_get(item, ["categories", "team"]), remote="remote" if "remote" in str(location).lower() else "unknown", japan_ok="yes" if "remote" in str(location).lower() else "unknown", description=strip_html(item.get("descriptionPlain") or item.get("description")), published_at=str(item.get("createdAt")) if item.get("createdAt") else None, raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class AshbyConnector(Connector):
    name = "ashby"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for board in settings.ashby_boards:
            try:
                data = await request_json(client, f"https://api.ashbyhq.com/posting-api/job-board/{board}", params={"includeCompensation": "true"}, headers=default_headers(settings))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                raise
            for item in data.get("jobs", []):
                compensation = ashby_compensation(item)
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("jobUrl") or item.get("applyUrl") or item.get("title")), title=item.get("title") or "Untitled", company=board, url=item.get("jobUrl") or item.get("applyUrl"), location=item.get("location") or ashby_address(item), compensation=compensation, contract_type=item.get("employmentType") or item.get("department"), remote="remote" if item.get("isRemote") else compact(item.get("workplaceType")), japan_ok="yes" if item.get("isRemote") else "unknown", description=strip_html(item.get("descriptionPlain") or item.get("descriptionHtml")), published_at=item.get("publishedAt"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class SerpApiConnector(Connector):
    name = "serpapi"
    endpoint = "https://serpapi.com/search.json"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        if not settings.serpapi_api_key:
            return []
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords[:5]:
            data = await request_json(client, self.endpoint, params={"engine": "google_jobs", "q": f"{keyword} remote contract", "hl": "en", "gl": "us", "api_key": settings.serpapi_api_key, "no_cache": "false"}, headers=default_headers(settings))
            for item in data.get("jobs_results", []):
                options = item.get("apply_options") or []
                url = (options[0] or {}).get("link") if options else item.get("share_link")
                extensions = item.get("extensions") or []
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("job_id") or item.get("share_link") or item.get("title")), title=item.get("title") or "Untitled", company=item.get("company_name"), url=url, location=item.get("location"), compensation=join_values([ext for ext in extensions if "$" in str(ext)]), contract_type=(item.get("detected_extensions") or {}).get("schedule_type") or join_values(extensions), remote="remote" if "remote" in str(item.get("location", "")).lower() else "unknown", japan_ok="unknown", description=strip_html(item.get("description")), published_at=(item.get("detected_extensions") or {}).get("posted_at"), raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


class FreelancerConnector(Connector):
    name = "freelancer"
    endpoint = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        if not settings.freelancer_oauth_token:
            return []
        headers = default_headers(settings)
        headers["Authorization"] = f"Bearer {settings.freelancer_oauth_token}"
        jobs: list[NormalizedJob] = []
        for keyword in settings.keywords[:5]:
            data = await request_json(client, self.endpoint, params={"query": keyword, "limit": min(settings.max_per_source, 50), "full_description": "true"}, headers=headers)
            result = data.get("result") or data
            for item in result.get("projects", result.get("items", [])):
                budget = item.get("budget") or {}
                currency = (budget.get("currency") or {}).get("code") or "USD"
                salary = salary_range(budget.get("minimum"), budget.get("maximum"), currency)
                jobs.append(NormalizedJob(source=self.name, external_id=str(item.get("id") or item.get("seo_url") or item.get("title")), title=item.get("title") or "Untitled", company=str(item.get("owner_id")) if item.get("owner_id") else None, url=f"https://www.freelancer.com/projects/{item.get('seo_url')}" if item.get("seo_url") else None, compensation=salary, contract_type=item.get("type"), remote="remote", japan_ok="unknown", description=strip_html(item.get("description")), published_at=str(item.get("submitdate")) if item.get("submitdate") else None, raw=item))
                if len(jobs) >= settings.max_per_source:
                    return jobs
            await polite_sleep(settings)
        return jobs


def salary_range(minimum: Any, maximum: Any, currency: str = "USD", period: str | None = None) -> str | None:
    suffix = f" per {period}" if period else ""
    if minimum and maximum:
        return f"{currency} {minimum:,} - {maximum:,}{suffix}"
    if minimum:
        return f"{currency} {minimum:,}+{suffix}"
    if maximum:
        return f"up to {currency} {maximum:,}{suffix}"
    return None


def ashby_address(item: dict[str, Any]) -> str | None:
    postal = ((item.get("address") or {}).get("postalAddress") or {})
    return join_values([postal.get("addressLocality"), postal.get("addressRegion"), postal.get("addressCountry")])


def ashby_compensation(item: dict[str, Any]) -> str | None:
    compensation = item.get("compensation") or {}
    if isinstance(compensation, dict):
        for key in ["compensationTierSummary", "scrapeableCompensationSalarySummary"]:
            if compensation.get(key):
                return str(compensation[key])
    for key in ["compensationTierSummary", "scrapeableCompensationSalarySummary"]:
        if item.get(key):
            return str(item[key])
    return None


def default_connectors() -> list[Connector]:
    return [HimalayasConnector(), JobicyConnector(), ArbeitnowConnector(), RemotiveConnector(), GreenhouseConnector(), LeverConnector(), AshbyConnector(), SerpApiConnector(), FreelancerConnector()]


@dataclass
class SourceResult:
    source: str
    fetched: int = 0
    saved: int = 0
    skipped: bool = False
    error: str | None = None


@dataclass
class CollectSummary:
    results: list[SourceResult] = field(default_factory=list)

    @property
    def saved_total(self) -> int:
        return sum(result.saved for result in self.results)

    @property
    def fetched_total(self) -> int:
        return sum(result.fetched for result in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {"fetched_total": self.fetched_total, "saved_total": self.saved_total, "results": [result.__dict__ for result in self.results]}


def dedupe_jobs(jobs: Iterable[NormalizedJob]) -> list[NormalizedJob]:
    seen: set[tuple[str, str]] = set()
    unique: list[NormalizedJob] = []
    for job in jobs:
        key = (job.source, str(job.external_id))
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


async def collect_all(*, settings: Settings | None = None, connectors: list[Connector] | None = None, force: bool = False) -> CollectSummary:
    settings = settings or Settings.from_env()
    connectors = connectors or default_connectors()
    init_db(settings.db_path)
    summary = CollectSummary()
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        with connect(settings.db_path) as conn:
            for connector in connectors:
                cooldown = settings.cooldown_hours.get(connector.name, 6)
                if not force and not source_due(conn, connector.name, cooldown):
                    summary.results.append(SourceResult(source=connector.name, skipped=True))
                    continue
                try:
                    fetched_jobs = dedupe_jobs(await connector.collect(client, settings))
                    saved = 0
                    for job in fetched_jobs:
                        enrich_job(job)
                        if upsert_job(conn, job):
                            saved += 1
                    record_source_run(conn, connector.name, status="success", count=len(fetched_jobs))
                    summary.results.append(SourceResult(source=connector.name, fetched=len(fetched_jobs), saved=saved))
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    record_source_run(conn, connector.name, status="error", count=0, error=message)
                    summary.results.append(SourceResult(source=connector.name, error=message))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect jobs into SQLite")
    parser.add_argument("--force", action="store_true", help="Ignore source cooldowns")
    return parser.parse_args()


def cli_main() -> None:
    args = parse_args()
    summary = asyncio.run(collect_all(force=args.force))
    print(summary.as_dict())
