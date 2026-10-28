"""Conservative opportunity triage and post-award subcontract gate.

No external communication or financial action is authorized by this module.
Evidence must come from the customer's actual contract, not the advertised job.
"""
from __future__ import annotations
import re
from typing import Any

EMPLOYMENT = re.compile(r"\b(full[- ]time|part[- ]time employee|salary|annual pay|permanent role|career opportunity|40 hours/week|20 hours/week|work from home job)\b", re.I)
MANUAL = re.compile(r"\b(telephone|cold call|voice[ -]?over|in[ -]?person|on[- ]site|physical|filming|record (?:your|a) voice|live training|drive to|warehouse|face[ -]?to[ -]?face|medical diagnosis|legal advice)\b", re.I)
DELIVERABLE = re.compile(r"\b(csv|spreadsheet|excel|google sheets|pdf|report|dataset|data cleaning|data extraction|research brief|supplier list|market research|api integration|python script|web scraping|automation workflow|webhook|fixed[- ]price|one[- ]off project|deliverables?)\b", re.I)
TECHNICAL = re.compile(r"\b(excel|spreadsheet|data extraction|data cleaning|research brief|supplier list|api integration|python script|automation workflow|webhook|csv|report|pdf|research)\b", re.I)

def triage(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("title") or "")
    description = str(row.get("description") or "")[:3000]
    typ = str(row.get("contract_type") or "")
    text = " ".join((title, description, typ))
    has_delivery = bool(DELIVERABLE.search(text))
    employment = bool(EMPLOYMENT.search(text)) or bool(re.search(r"\b(manager|sales representative|full[- ]stack engineer|assistant|tutor)\b", title, re.I) and not has_delivery)
    requires_human = bool(MANUAL.search(text))
    # "Freelancer/contractor" without a paid, defined deliverable does not create a contract.
    scope = bool(has_delivery and not employment)
    ai_only = bool(scope and TECHNICAL.search(text) and not requires_human)
    return {
        "project_qualified": scope,
        "delivery_mode": "ai_first_candidate" if ai_only else ("hybrid_review" if scope else "unqualified"),
        "ai_only_candidate": ai_only,
        "requires_human": requires_human,
        "reason": ("employment_or_no_fixed_deliverable" if not scope else
                   "human_physical_or_synchronous_requirement" if requires_human else
                   "digital_deliverable_candidate"),
        "confirmed_ai_deliverable": False,  # Only after seeing actual acceptance criteria and legal rights.
    }

def subcontract_gate(contract: dict[str, Any] | None) -> dict[str, Any]:
    """Fail closed until a real signed/awarded contract and authorized scope exist."""
    contract = contract or {}
    required = {
        "contract_awarded": contract.get("state") in ("awarded", "active"),
        "provider_id_verified": isinstance(contract.get("provider_contract_id"), str)
                                and len(contract.get("provider_contract_id", "").strip()) >= 6,
        "client_subcontract_consent": contract.get("subcontract_consent") is True,
        "platform_allows_subcontracting": contract.get("provider_policy_allows") is True,
        "workforce_required": contract.get("ai_delivery_failed") is True,
        "funded_milestone_verified": contract.get("funded") is True,
    }
    allowed = all(required.values())
    return {"may_search_workers": allowed, "may_commit_money": False,
            "requirements": required, "reason": "contract_gated" if not allowed else
            "worker_search_only_after_award"}
