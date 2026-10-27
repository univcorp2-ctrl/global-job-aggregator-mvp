"""Market hypotheses and unit economics may never masquerade as live bookings."""
import json

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.market import read_market_matrix, compare_opportunities, scenario_roi


def test_complete_matrix_scores_weights_and_distinguishes_not_verified():
    doc=read_market_matrix()
    assert len(doc["opportunities"])>=15
    assert sum(doc["weights"].values())==100
    assert len({x["id"] for x in doc["opportunities"]})==len(doc["opportunities"])
    assert all(x["actual_accepted_clients"]==0 for x in doc["opportunities"])
    assert not any(x["worker_supply_is_verified"] for x in doc["opportunities"])
    assert not any(x["automation_rate_is_measured"] for x in doc["opportunities"])


def test_ranking_is_scored_judgement_not_win_probability():
    response=compare_opportunities(limit=5)
    scores=[r["priority_score"] for r in response["opportunities"]]
    assert scores==sorted(scores,reverse=True)
    assert "not measured" in response["score_semantics"].lower()
    assert "not verified" in response["supply_semantics"].lower()


def test_low_margin_case_no_false_positive():
    result=scenario_roi(customer_price=100000,contractor_cost=60000,
                        ai_api_cost=10000,human_qa_cost=25000,
                        acquisition_cost=12000,support_cost=5000)
    assert result["estimated_contribution"]==-12000
    assert result["estimated_contribution_margin_pct"]==-12
    assert result["value_verified"] is False
    assert result["subcontract_rights_verified"] is False


def test_zero_revenue_margin_does_not_divide_by_zero():
    result=scenario_roi(customer_price=0)
    assert result["estimated_contribution_margin_pct"] is None


def test_calculated_client_savings_are_assumptions():
    result=scenario_roi(customer_price=148000,contractor_cost=40000,
                        ai_api_cost=3000,human_qa_cost=20000,marketplace_fee=12000,
                        acquisition_cost=15000,support_cost=8000,contingency=10000,
                        hours_before=80,estimated_hours_after=40,labor_cost_per_hour=2500)
    assert result["estimated_total_cost"]==108000
    assert result["estimated_contribution"]==40000
    assert result["estimated_client_labor_savings"]==100000
    assert result["scenario_not_actual"] is True


def test_bad_score_cannot_pass_validator(tmp_path):
    original=read_market_matrix()
    original["opportunities"][0]["priority_score"]=1
    dest=tmp_path/"bad.json"
    dest.write_text(json.dumps(original),encoding="utf-8")
    with pytest.raises(ValueError,match="mismatch"):
        read_market_matrix(dest)


def test_market_screen_public_but_private_scenario_requires_auth(monkeypatch):
    monkeypatch.delenv("WORKER_DB_TOKEN",raising=False)
    with TestClient(app) as client:
        data=client.get("/api/market/opportunities?limit=3")
        assert data.status_code==200
        assert data.json()["total"]>=15
        assert len(data.json()["opportunities"])==3
        assert client.get("/market").status_code==200
        response=client.post("/api/market/scenario",json={"customer_price":100000})
        assert response.status_code==401


def test_private_scenario_returns_calculation_without_claiming_earnings(monkeypatch):
    monkeypatch.setenv("WORKER_DB_TOKEN","only-a-test")
    with TestClient(app) as client:
        r=client.post("/api/market/scenario",
                      headers={"x-worker-token":"only-a-test"},
                      json={"customer_price":80000,"contractor_cost":30000})
    assert r.status_code==200
    assert r.json()["estimated_contribution"]==50000
    assert r.json()["value_verified"] is False
