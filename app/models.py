from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
        now = utc_now()
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
            "updated_at": now,
        }
