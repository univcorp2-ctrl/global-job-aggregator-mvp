"""Opportunity-category evidence inventory, scoring and conservative ROI calculator.

Research scores are *judgemental hypotheses*, not market size or win probability.
Live worker search results may not be treated as licensed supply without OAuth.
"""
from __future__ import annotations

import json
from pathlib import Path

RESEARCH_PATH = Path(__file__).resolve().parent.parent / "research" / "market_opportunity_matrix_2026-10-27.json"


def read_market_matrix(path: Path | None = None) -> dict:
    data = json.loads((path or RESEARCH_PATH).read_text(encoding="utf-8"))
    weights = data["weights"]
    if sum(weights.values()) != 100:
        raise ValueError("Market weights must sum to 100")
    opportunities = data["opportunities"]
    ids = [o["id"] for o in opportunities]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate opportunity category")
    for o in opportunities:
        for key in weights:
            if not isinstance(o[key], int) or not 1 <= o[key] <= 5:
                raise ValueError(f"Invalid judgement score {o['id']}:{key}")
        computed = round(sum(o[key] * weight / 5 for key,weight in weights.items()), 3)
        if abs(computed - o["priority_score"]) > 0.001:
            raise ValueError(f"Score calculation mismatch {o['id']}")
        if o["worker_supply_is_verified"] or o["automation_rate_is_measured"]:
            raise ValueError("Missing live validation cannot be assumed true")
    return data


def compare_opportunities(limit: int = 20, market: str | None = None) -> dict:
    doc = read_market_matrix()
    items = [i for i in doc["opportunities"] if not market or
             market.lower() in i["geography"].lower() or "日本/海外" == i["geography"]]
    items.sort(key=lambda x: x["priority_score"],reverse=True)
    return {"as_of":doc["as_of"],"weights":doc["weights"],
            "score_semantics":doc["score_semantics"],
            "supply_semantics":doc["supply_semantics"],
            "source_registry":doc["source_registry"],
            "total":len(items),"opportunities":items[:max(1,min(limit,50))]}


def scenario_roi(
    *, customer_price: float,
    contractor_cost: float = 0,
    ai_api_cost: float = 0,
    human_qa_cost: float = 0,
    marketplace_fee: float = 0,
    acquisition_cost: float = 0,
    support_cost: float = 0,
    contingency: float = 0,
    hours_before: float = 0,
    estimated_hours_after: float = 0,
    labor_cost_per_hour: float = 0,
) -> dict:
    costs = (contractor_cost, ai_api_cost, human_qa_cost,
             marketplace_fee, acquisition_cost, support_cost, contingency)
    values = (customer_price, *costs, hours_before, estimated_hours_after, labor_cost_per_hour)
    if any(v < 0 or not isinstance(v,(int,float)) for v in values):
        raise ValueError("Costs, price and hours must be nonnegative numbers")
    total_cost = sum(costs)
    contribution = customer_price - total_cost
    margin = round(100 * contribution / customer_price, 2) if customer_price else None
    saved_hours = hours_before - estimated_hours_after
    saving = saved_hours * labor_cost_per_hour
    return {
        "scenario_not_actual":True, "currency":"JPY",
        "estimated_revenue":customer_price,"estimated_total_cost":total_cost,
        "estimated_contribution":round(contribution,2),
        "estimated_contribution_margin_pct":margin,
        "estimated_hours_saved":round(saved_hours,2),
        "estimated_client_labor_savings":round(saving,2),
        "value_verified":False, "worker_supply_verified":False,
        "subcontract_rights_verified":False,
        "warnings":[
            "This is a unit-economics scenario, not realized revenue or profit.",
            "Source platform commission, taxes, VAT, support incidents, refund and AI token variation may differ.",
            "AI-completion share is an unverified hypothesis. Baseline, holdout and error rates must be measured.",
        ]
    }
