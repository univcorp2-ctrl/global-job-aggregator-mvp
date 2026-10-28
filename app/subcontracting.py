"""Backup specialist planning; capability evidence is not a worker commitment.

No profiles, messaging, external orders, or payment operations. All illustrative
rates require fresh platform-native quotes and permissions before use.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class SpecialistScenario:
    task_category: str
    estimated_hours: float
    indicated_hourly_rate_usd: float
    customer_budget_usd: float
    platform_fee_usd: float = 0
    qa_reserve_usd: float = 0
    other_costs_usd: float = 0
    original_client_subcontract_approved: bool = False
    original_platform_allows_subcontract: bool = False
    worker_accepted_terms: bool = False
    confidentiality_approved: bool = False
    worker_quote_verified: bool = False
    required_outcome_measurable: bool = False

def subcontract_backup_plan(case: SpecialistScenario) -> dict:
    allowed={"excel_formula_qa","n8n_make_specialist","ui_polish"}
    if case.task_category not in allowed:
        raise ValueError("Unsupported specialist category")
    amounts=(case.estimated_hours,case.indicated_hourly_rate_usd,
             case.customer_budget_usd,case.platform_fee_usd,
             case.qa_reserve_usd,case.other_costs_usd)
    if any(not isinstance(x,(int,float)) or x<0 or x>1e7 for x in amounts):
        raise ValueError("Cost and workload must be finite nonnegative values")
    estimated_supplier_cost=round(case.estimated_hours*case.indicated_hourly_rate_usd,2)
    estimated_total_cost=round(estimated_supplier_cost+case.platform_fee_usd+
                               case.qa_reserve_usd+case.other_costs_usd,2)
    gross=round(case.customer_budget_usd-estimated_total_cost,2)
    gates={
        "client_written_subcontract_permission":case.original_client_subcontract_approved,
        "source_platform_permits":case.original_platform_allows_subcontract,
        "worker_opt_in_and_terms":case.worker_accepted_terms,
        "client_confidentiality_permission":case.confidentiality_approved,
        "written_platform_native_quote":case.worker_quote_verified,
        "measurable_acceptance_criteria":case.required_outcome_measurable,
        "positive_budget":gross>0,
    }
    ready=all(gates.values())
    return {
        "specialist_category":case.task_category,
        "estimated_supplier_cost_usd":estimated_supplier_cost,
        "estimated_total_cost_usd":estimated_total_cost,
        "estimated_contribution_usd":gross,
        "estimate_not_verified_quote":not case.worker_quote_verified,
        "ready_for_owner_to_review_order":ready,
        "status":"owner_approval_required" if ready else "hold_do_not_contact_or_purchase",
        "missing":[k for k,v in gates.items() if not v],
        "sent_messages":0,
        "placed_orders":0,
        "next_step":"Get official platform quote and written permissions; owner reviews one task-specific native contract.",
    }

def indicative_categories() -> list[dict]:
    """Observed profiles in official marketplace search, not actual accepted quotes.

    Checked Oct 28 JST; prices in USD/hr, range from only first returned sample,
    not a market-wide wage estimate, and no worker identities are persisted.
    """
    return [
      {"skill":"excel_formula_qa","sample_profiles":10,
       "sample_hourly_usd_min":8.0,"sample_hourly_usd_max":25.0,
       "search":"Excel VBA","status":"uncommitted_public_marketplace_profiles"},
      {"skill":"n8n_make_specialist","sample_profiles":10,
       "sample_hourly_usd_min":8.0,"sample_hourly_usd_max":25.75,
       "search":"n8n automation","status":"uncommitted_public_marketplace_profiles"},
      {"skill":"ui_polish","sample_profiles":10,
       "sample_hourly_usd_min":8.0,"sample_hourly_usd_max":30.0,
       "search":"dashboard UI design","status":"uncommitted_public_marketplace_profiles"},
    ]
