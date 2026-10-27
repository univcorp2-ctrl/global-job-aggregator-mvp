"""Deterministic small-job processing, no customer data or messaging."""
import csv
import io
import pytest
from app.simple_jobs import clean_csv, round_robin_cross_teams


def test_clean_csv_dedupes_and_reports_missing_values():
    csv_text="Name, Amount,Email\n Alice , 20 ,a@example.com\nAlice,20,a@example.com\nBob,,b@example.com\n"
    data=clean_csv(csv_text,dedupe_columns=["Name","Email"])
    assert data["report"]["input_rows"]==3
    assert data["report"]["output_rows"]==2
    assert data["report"]["duplicates_excluded"]==1
    assert data["report"]["anomaly_count"]==2
    assert data["status"]=="prepared_requires_client_qa"


def test_clean_csv_neutralizes_spreadsheet_formula_injection():
    rows=clean_csv("Name,Value\nBob,=IMPORTXML(\"https://example.invalid\")\n")
    line=list(csv.DictReader(io.StringIO(rows["clean_csv"])))[0]["Value"]
    assert line.startswith("'=")
    assert "IMPORTXML" in line


def test_clean_csv_blocks_ambiguous_headers():
    with pytest.raises(ValueError,match="Ambiguous"):
        clean_csv("Name,Name\nAlice,Bob\n")


@pytest.mark.parametrize("na,nb",[(4,4),(20,24),(8,12),(24,24)])
def test_round_robin_cross_team_fair_all_pairs_once(na,nb):
    a=[f"A{i}" for i in range(na)]
    b=[f"B{i}" for i in range(nb)]
    data=round_robin_cross_teams(a,b)
    assert data["match_count"]==na*nb
    assert data["round_count"]==max(na,nb)
    assert len({(x["team_a_player"],x["team_b_player"]) for x in data["matches"]})==na*nb
    for n in range(1,data["round_count"]+1):
        games=[x for x in data["matches"] if x["round"]==n]
        assert len(games)==len({x["team_a_player"] for x in games})
        assert len(games)==len({x["team_b_player"] for x in games})
    assert data["customer_rule_confirmed"] is False


def test_round_robin_rejects_duplicate_people_and_undersized_bracket():
    with pytest.raises(ValueError,match="unique"):
        round_robin_cross_teams(["A"]*4,["B1","B2","B3","B4"])
    with pytest.raises(ValueError,match="8-48"):
        round_robin_cross_teams(["A1","A2"],["B1","B2"])
