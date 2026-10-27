"""Delegation cannot be approved by margin alone."""
from fastapi.testclient import TestClient
from app.delegation import DelegationInput,evaluate_delegation
from app.main import app


def test_price_margin_does_not_override_missing_permissions():
    r=evaluate_delegation(DelegationInput(customer_price=100000,
        supplier_quote=55000,platform_fees=9000,qa_reserve=6000,fx_buffer=2000))
    assert r["estimated_gross_profit"]==28000
    assert r["estimated_margin_pct"]==28
    assert r["status"]=="blocked_requirements_unmet"
    assert not r["gates"]["client_subcontract_approval"]
    assert r["can_send_contact_automatically"] is False


def test_even_all_permitted_no_automated_contract_or_dispatch():
    r=evaluate_delegation(DelegationInput(customer_price=100000,
        supplier_quote=50000,platform_fees=10000,qa_reserve=5000,
        subcontract_approved_by_client=True,worker_agreed=True,
        platform_terms_verified=True,data_sharing_approved=True,
        written_terms_ready=True))
    assert r["status"]=="review_ready_not_contracted"
    assert r["estimated_gross_profit"]==35000
    assert r["can_sign_or_pay_automatically"] is False
    assert r["can_send_contact_automatically"] is False


def test_cross_currency_cost_needs_external_fx_not_made_up():
    r=evaluate_delegation(DelegationInput(customer_price=100000,
        supplier_quote=500,client_currency="JPY",worker_currency="USD"))
    assert r["estimated_gross_profit"] is None
    assert r["status"]=="blocked_requirements_unmet"
    assert "currency_conversion_validated" in r["missing_gates"]


def test_api_requires_owner_secret(monkeypatch):
    monkeypatch.delenv("WORKER_DB_TOKEN",raising=False)
    with TestClient(app) as client:
        assert client.post("/api/delegation/evaluate",
            json={"customer_price":100000,"supplier_quote":50000}).status_code==401


def test_api_returns_nonbinding_estimate(monkeypatch):
    monkeypatch.setenv("WORKER_DB_TOKEN","test-evaluation-only")
    with TestClient(app) as client:
        response=client.post("/api/delegation/evaluate",
            json={"customer_price":100000,"supplier_quote":65000,"qa_reserve":5000},
            headers={"x-worker-token":"test-evaluation-only"})
    assert response.status_code==200
    assert response.json()["estimated_gross_profit"]==30000
    assert response.json()["status"]=="blocked_requirements_unmet"
