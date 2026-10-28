"""Backup outsourcing budget and permissions tests."""
import pytest
from fastapi.testclient import TestClient
from app import main
from app.subcontracting import SpecialistScenario, subcontract_backup_plan, indicative_categories


def test_observed_marketplace_rates_are_not_worker_quotes():
    categories=indicative_categories()
    assert {x["skill"] for x in categories} == {"excel_formula_qa","n8n_make_specialist","ui_polish"}
    assert all(x["sample_profiles"]==10 for x in categories)
    assert all(x["status"]=="uncommitted_public_marketplace_profiles" for x in categories)


def test_cheap_job_blocks_professional_subcontract():
    plan=subcontract_backup_plan(SpecialistScenario(
        task_category="excel_formula_qa",estimated_hours=2,
        indicated_hourly_rate_usd=15,customer_budget_usd=50,
        platform_fee_usd=8,qa_reserve_usd=10,other_costs_usd=5))
    assert plan["estimated_total_cost_usd"]==53
    assert plan["estimated_contribution_usd"]==-3
    assert plan["ready_for_owner_to_review_order"] is False
    assert "positive_budget" in plan["missing"]
    assert plan["sent_messages"]==0 and plan["placed_orders"]==0


def test_price_is_insufficient_without_permission():
    plan=subcontract_backup_plan(SpecialistScenario(
        task_category="n8n_make_specialist",estimated_hours=1,
        indicated_hourly_rate_usd=10,customer_budget_usd=300))
    assert plan["estimated_contribution_usd"]==290
    assert plan["ready_for_owner_to_review_order"] is False
    assert "worker_opt_in_and_terms" in plan["missing"]
    assert "client_written_subcontract_permission" in plan["missing"]


def test_all_permission_still_requires_owner_review_no_auto_order():
    plan=subcontract_backup_plan(SpecialistScenario(
        task_category="ui_polish",estimated_hours=1,
        indicated_hourly_rate_usd=10,customer_budget_usd=300,
        original_client_subcontract_approved=True,
        original_platform_allows_subcontract=True,
        worker_accepted_terms=True,confidentiality_approved=True,
        worker_quote_verified=True,required_outcome_measurable=True))
    assert plan["ready_for_owner_to_review_order"] is True
    assert plan["status"]=="owner_approval_required"
    assert plan["placed_orders"]==0


def test_invalid_category_blocked():
    with pytest.raises(ValueError,match="Unsupported"):
        subcontract_backup_plan(SpecialistScenario(task_category="unspecified",
            estimated_hours=0,indicated_hourly_rate_usd=0,customer_budget_usd=100))


def test_owner_only_api_gate(monkeypatch):
    monkeypatch.delenv("WORKER_DB_TOKEN",raising=False)
    with TestClient(main.app) as client:
        assert client.get("/api/applications/specialist-capabilities").status_code==401
        assert client.post("/api/applications/subcontract-plan",
            json={"task_category":"excel_formula_qa","estimated_hours":2,
                  "indicated_hourly_rate_usd":10,"customer_budget_usd":100}).status_code==401


def test_api_nonbinding_quote(monkeypatch):
    monkeypatch.setenv("WORKER_DB_TOKEN","test-secret-only")
    with TestClient(main.app) as client:
        h={"x-worker-token":"test-secret-only"}
        response=client.post("/api/applications/subcontract-plan",headers=h,
            json={"task_category":"excel_formula_qa","estimated_hours":2,
                  "indicated_hourly_rate_usd":10,"customer_budget_usd":100})
        assert response.status_code==200
        assert response.json()["status"]=="hold_do_not_contact_or_purchase"
        assert response.json()["estimated_contribution_usd"]==80
        r=client.get("/api/applications/specialist-capabilities",headers=h)
        assert r.status_code==200
        assert len(r.json()["capabilities"])==3
