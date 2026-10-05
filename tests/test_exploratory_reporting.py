import copy

from fleetsense.common import ROOT, read_config, read_json
from fleetsense.reporting import claims, presentation, tuning_feasibility
from scripts.exploratory_tradeoffs import analyze, pareto
from scripts.refresh_reports import refresh


def point(parameter, availability, failures, waste):
    return {"policy": "FC", "parameter": parameter, "availability_pct": availability,
            "failures_per_aircraft_year": failures, "wasted_life_cycles": waste}


def test_pareto_strict_dominance_ties_and_waste():
    rows = [point(1, 97, 0.2, 30), point(2, 96, 0.3, 10),
            point(3, 96, 0.3, 10), point(4, 95, 0.4, 20)]
    original = copy.deepcopy(rows)
    assert [row["parameter"] for row in pareto(rows)] == [1]
    assert [row["parameter"] for row in pareto(rows, True)] == [1, 2, 3]
    assert rows == original


def test_pareto_missing_waste():
    rows = [point(1, 97, 0.2, None), point(2, 96, 0.3, 10)]
    assert pareto(rows) == [rows[0]]
    assert pareto(rows, True) == [rows[1]]


def test_actual_dev_feasibility_and_no_policy_change():
    tuning = read_json(ROOT / "results/tuning.json")
    frontier = read_json(ROOT / "results/frontier.json")
    original = copy.deepcopy(tuning)
    budget = read_config()["tuning"]["failure_budget"]
    feasibility = tuning_feasibility(tuning, budget)
    assert {policy: row["candidate_count"] for policy, row in feasibility.items()} == {"HT": 17, "CT": 20, "FC": 8}
    assert all(row["feasible_count"] == 0 and row["selection_mode"] == "fewest_failures_fallback"
               for row in feasibility.values())
    report = analyze(tuning, frontier, budget)
    assert report["final_policy_changed"] is False
    assert report["evaluation_kind"] == "exploratory_reporting_only"
    assert report["test_reporting_only"]["candidate_count"] == len(frontier)
    assert tuning == original


def test_disclosures_survive_deck_truncation():
    summary = read_json(ROOT / "results/summary.json")
    report = presentation(summary)
    assert "0/17" in report["facts"][0] and "fallback" in report["facts"][0]
    assert "No development candidate" in report["limitations"][0]
    assert "REFUTED" in report["limitations"][1]
    assert any(row["label"] == "Tests passed (includes UI)" for row in report["metrics"])
    assert any(row["status"] == "Deviation" and "failure budget" in row["claim"] for row in claims(summary))


def test_refresh_preserves_all_measured_fields_and_existing_deviations():
    summary = read_json(ROOT / "results/summary.json")
    summary.setdefault("deviations", []).append({"kind": "existing", "reason": "preserve"})
    original = copy.deepcopy(summary)
    result = refresh(summary)
    derived = {"claims", "deviations", "presentation", "study_design"}
    assert {key: value for key, value in result.items() if key not in derived} == {
        key: value for key, value in original.items() if key not in derived}
    assert result["verdict"] == "REFUTED"
    assert "frozen fallback" in result["study_design"]["scope_caveat"]
    warning = result["study_design"]["scope_warning"]
    assert 23 <= len(warning.split()) <= 28
    assert "No development policy met the failure budget" in warning
    assert "fewest-failures fallbacks" in warning
    assert "not forecasting in general" in warning
    assert {"kind": "existing", "reason": "preserve"} in result["deviations"]
    refreshed = copy.deepcopy(result)
    assert refresh(result) == refreshed
