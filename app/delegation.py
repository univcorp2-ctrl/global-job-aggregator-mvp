"""Pre-contract delegation feasibility. All amounts are hypothetical until verified."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class DelegationInput:
    customer_price: float
    supplier_quote: float
    platform_fees: float = 0
    qa_reserve: float = 0
    fx_buffer: float = 0
    subcontract_approved_by_client: bool = False
    worker_agreed: bool = False
    platform_terms_verified: bool = False
    data_sharing_approved: bool = False
    written_terms_ready: bool = False
    client_currency: str = "JPY"
    worker_currency: str = "JPY"


def evaluate_delegation(p: DelegationInput) -> dict:
    if p.customer_price < 0 or p.supplier_quote < 0:
        raise ValueError("Amounts must be nonnegative")
    if any(x < 0 for x in (p.platform_fees,p.qa_reserve,p.fx_buffer)):
        raise ValueError("Fees/reserves must be nonnegative")
    same_currency = p.client_currency.upper() == p.worker_currency.upper()
    cost = p.supplier_quote + p.platform_fees + p.qa_reserve + p.fx_buffer if same_currency else None
    gross_profit = p.customer_price - cost if cost is not None else None
    margin = round(100 * gross_profit / p.customer_price,2) if gross_profit is not None and p.customer_price else None
    gates = {
       "client_subcontract_approval":p.subcontract_approved_by_client,
       "worker_consent":p.worker_agreed,
       "platform_terms_allow_transaction":p.platform_terms_verified,
       "client_confidential_data_sharing_approval":p.data_sharing_approved,
       "written_worker_terms_ready":p.written_terms_ready,
       "currency_conversion_validated":same_currency,
    }
    ready = all(gates.values()) and gross_profit is not None and gross_profit > 0
    return {
       "status":"review_ready_not_contracted" if ready else "blocked_requirements_unmet",
       "can_send_contact_automatically":False,
       "can_sign_or_pay_automatically":False,
       "currency":p.client_currency.upper(),
       "total_estimated_cost":round(cost,2) if cost is not None else None,
       "estimated_gross_profit":round(gross_profit,2) if gross_profit is not None else None,
       "estimated_margin_pct":margin,
       "gates":gates,
       "missing_gates":[name for name,allowed in gates.items() if not allowed],
       "notes":[
         "Numbers are user assumptions, not verified marketplace rates or tax-adjusted net income.",
         "Cross-platform subcontracting can be barred by an original client contract or marketplace terms.",
         "Japan freelancer transactions require written/electronic terms and payment deadline compliance.",
       ]
    }
