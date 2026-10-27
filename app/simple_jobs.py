"""AI-first starter deliverables for bounded spreadsheet jobs.

These are deterministic processing cores, not claims of client delivery.
Real customer files require written scope, explicit upload authorization and QA.
"""
from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass


def _safe_cell(value: str) -> str:
    """Neutralize spreadsheet formula injection for untrusted CSV cells."""
    value=value.strip()
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def clean_csv(csv_text: str, *, dedupe_columns: list[str] | None = None) -> dict:
    """Clean whitespace, preserve columns, identify duplicates and missing data.

    Rows are not silently deleted for missing values; a QC report is returned.
    Duplicate matches use exact normalized values for the configured keys.
    """
    if len(csv_text) > 5_000_000:
        raise ValueError("CSV over 5 MB needs an explicit batch scope")
    csv_text=csv_text.lstrip("\ufeff")
    reader=csv.DictReader(io.StringIO(csv_text, newline=""))
    fields=reader.fieldnames or []
    if not fields or len(fields)>100:
        raise ValueError("Valid CSV header with up to 100 columns required")
    fields=[h.strip() for h in fields]
    if len(set(fields))!=len(fields) or any(not h for h in fields):
        raise ValueError("Ambiguous or empty CSV headers")
    keys=dedupe_columns or fields
    if not all(k in fields for k in keys):
        raise ValueError("Dedupe keys absent from header")
    seen=set()
    clean=[]
    anomalies=[]
    duplicates=0
    for ix,item in enumerate(reader,start=2):
        if ix>50_001:
            raise ValueError("Over 50,000 data rows: batch processing required")
        if None in item:  # extra columns beyond header
            anomalies.append({"row":ix,"type":"extra_fields"})
        vals={}
        for h,raw in item.items():
            if h is None:continue
            key=h.strip()
            vals[key]=_safe_cell(raw or "")
        missing=[k for k,v in vals.items() if not v]
        if missing:
            anomalies.append({"row":ix,"type":"missing_values","columns":missing})
        signature=tuple(vals.get(k,"").casefold() for k in keys)
        if signature in seen:
            duplicates+=1
            anomalies.append({"row":ix,"type":"duplicate","columns":keys})
            continue
        seen.add(signature)
        clean.append(vals)
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n")
    writer.writeheader()
    writer.writerows(clean)
    return {
      "clean_csv":stream.getvalue(),
      "report":{"input_rows":ix-1 if 'ix' in locals() else 0,
                "output_rows":len(clean),
                "duplicates_excluded":duplicates,
                "anomaly_count":len(anomalies),
                "anomalies":anomalies[:500]},
      "status":"prepared_requires_client_qa",
    }


def round_robin_cross_teams(team_a: list[str], team_b: list[str]) -> dict:
    """All Team A vs Team B encounters, one match per opponent pair.

    A real client's specification must resolve whether they intended this
    cross-team pairing or each-team full round-robin before use.
    """
    na,nb=len(team_a),len(team_b)
    if not 1<=na<=24 or not 1<=nb<=24 or not 8<=na+nb<=48:
        raise ValueError("8-48 total players, 1-24 per team required")
    names=[name.strip() for name in [*team_a,*team_b]]
    if any(not s for s in names) or len({s.casefold() for s in names})!=len(names):
        raise ValueError("Each player must have a unique nonempty name")
    rounds=max(na,nb)
    games=[{"round":(i+j)%rounds+1,"team_a_player":a.strip(),
            "team_b_player":b.strip()} for i,a in enumerate(team_a)
                                          for j,b in enumerate(team_b)]
    games.sort(key=lambda m:(m["round"],m["team_a_player"],m["team_b_player"]))
    # No player appears more than once per round.
    for round_no in range(1,rounds+1):
        matches=[m for m in games if m["round"]==round_no]
        assert len({m["team_a_player"] for m in matches})==len(matches)
        assert len({m["team_b_player"] for m in matches})==len(matches)
    return {"format":"cross_team_full_round_robin","matches":games,
            "match_count":len(games),"round_count":rounds,
            "customer_rule_confirmed":False,
            "delivery_status":"algorithm_test_only_not_client_delivered"}
