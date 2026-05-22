from __future__ import annotations

import re

from app.models import NormalizedJob
from app.utils import compact, strip_html

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

NEGATIVE_PATTERNS = ["unpaid", "volunteer", "commission only"]
HOURLY_RE = re.compile(r"(?:\$|USD\s*)?(\d{2,4})(?:\.\d+)?\s*(?:/|per)?\s*(?:hour|hr)", re.I)
ANNUAL_RE = re.compile(r"(?:\$|USD\s*)?(\d{2,3})(?:,?\d{3}|k)\b", re.I)


def detect_skills(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for skill in SKILL_PATTERNS:
        if skill.lower() in lowered:
            found.append(skill)
    return found


def score_text(text: str) -> float:
    lowered = text.lower()
    score = 0
    for skill, weight in SKILL_PATTERNS.items():
        if skill.lower() in lowered:
            score += weight
    for pattern in NEGATIVE_PATTERNS:
        if pattern in lowered:
            score -= 10
    return max(0.0, min(100.0, float(score)))


def estimate_monthly_income(compensation: str | None) -> str | None:
    if not compensation:
        return None
    text = compensation.replace(",", "")
    hourly = [int(match) for match in HOURLY_RE.findall(text)]
    if hourly:
        average_hourly = sum(hourly) / len(hourly)
        monthly = average_hourly * 120
        return f"USD {monthly:,.0f}/mo estimate at 120h"
    annual = []
    for match in ANNUAL_RE.findall(text):
        number = int(match)
        if number < 1000:
            number *= 1000
        annual.append(number)
    if annual:
        monthly = (sum(annual) / len(annual)) / 12
        return f"USD {monthly:,.0f}/mo estimate from annual range"
    return None


def priority(ai_relevance: float, fit_score: float, compensation: str | None) -> str:
    pay_bonus = 10 if compensation and any(token in compensation.lower() for token in ["usd", "$", "hour"]) else 0
    total = ai_relevance + fit_score + pay_bonus
    if total >= 85:
        return "A"
    if total >= 55:
        return "B"
    return "C"


def build_proposal(job: NormalizedJob) -> str:
    skills = ", ".join(job.required_skills[:5]) or "AI automation and data workflows"
    title = compact(job.title) or "this role"
    company = f" at {job.company}" if job.company else ""
    return (
        f"Hi, I found your {title}{company} opportunity and it looks aligned with my work in "
        f"{skills}. I can help turn fragmented web/API data into reliable automations, dashboards, "
        "and business-ready reports using Python, APIs, AI tools, and spreadsheet/database workflows. "
        "I would start by clarifying the target outcome, building a small reliable pipeline, then adding "
        "monitoring and a clean handoff so the system stays maintainable."
    )


def enrich_job(job: NormalizedJob) -> NormalizedJob:
    text = " ".join(
        value
        for value in [job.title, job.company, job.description, job.contract_type, job.compensation]
        if value
    )
    text = strip_html(text) or ""
    skills = detect_skills(text)
    existing = list(dict.fromkeys(job.required_skills + skills))
    job.required_skills = existing
    job.ai_relevance = score_text(text)
    job.fit_score = min(100.0, job.ai_relevance + (15 if "Real Estate" in existing else 0))
    job.expected_monthly_income = job.expected_monthly_income or estimate_monthly_income(job.compensation)
    job.application_priority = priority(job.ai_relevance, job.fit_score, job.compensation)
    job.proposal_draft = job.proposal_draft or build_proposal(job)
    return job
