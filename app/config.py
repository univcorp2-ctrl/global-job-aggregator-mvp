from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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
    def from_env(cls) -> "Settings":
        keywords = parse_csv(os.getenv("JOB_KEYWORDS")) or DEFAULT_KEYWORDS.copy()
        return cls(
            db_path=Path(os.getenv("DB_PATH", "data/jobs.db")),
            keywords=keywords,
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
