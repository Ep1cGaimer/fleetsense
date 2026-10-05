import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, assert_lock, read_config, read_json, sha256, write_json
from fleetsense.reporting import tuning_feasibility


def pareto(rows, include_waste=False):
    def objectives(row):
        values = [-row["availability_pct"], row["failures_per_aircraft_year"]]
        if include_waste:
            values.append(row["wasted_life_cycles"])
        return values

    eligible = [row for row in rows if not include_waste or row["wasted_life_cycles"] is not None]
    return [dict(row) for row in eligible if not any(
        all(other_value <= value for other_value, value in zip(objectives(other), objectives(row)))
        and any(other_value < value for other_value, value in zip(objectives(other), objectives(row)))
        for other in eligible)]


def describe(rows, budget):
    return {"candidate_count": len(rows),
            "feasible_count": sum(row["failures_per_aircraft_year"] <= budget for row in rows),
            "availability_failure_pareto": pareto(rows),
            "availability_failure_waste_pareto": pareto(rows, include_waste=True),
            "missing_waste_count": sum(row["wasted_life_cycles"] is None for row in rows)}


def analyze(tuning, frontier, budget):
    dev = describe(tuning["rows"], budget)
    dev["policies"] = tuning_feasibility(tuning, budget)
    test = describe(frontier, budget)
    for policy in ("HT", "CT", "FC"):
        dev["policies"][policy].update(describe([row for row in tuning["rows"] if row["policy"] == policy], budget))
    test["policies"] = {policy: describe([row for row in frontier if row["policy"] == policy], budget)
                        for policy in ("HT", "CT", "FC")}
    return {"schema_version": 1, "evaluation_kind": "exploratory_reporting_only",
            "failure_budget": budget, "development": dev, "test_reporting_only": test,
            "objectives": {"availability_pct": "maximise", "failures_per_aircraft_year": "minimise",
                           "wasted_life_cycles": "minimise (additional three-objective frontier)"},
            "limitations": ["Post-result description of existing aggregates, not a new experiment or confirmatory analysis.",
                            "Test frontier must not be used to retune thresholds or choose a new final policy.",
                            "Pareto membership uses point estimates only; no uncertainty or significance is established.",
                            "Rows with missing wasted life are excluded only from the three-objective frontier.",
                            "Budget feasibility is confined to the measured grids and scenarios, not universal feasibility."],
            "final_policy_changed": False}


def main():
    assert_lock()
    tuning_path = ROOT / "results/tuning.json"
    frontier_path = ROOT / "results/frontier.json"
    report = analyze(read_json(tuning_path), read_json(frontier_path), read_config()["tuning"]["failure_budget"])
    report["sources"] = {str(path.relative_to(ROOT)): sha256(path) for path in (tuning_path, frontier_path)}
    write_json(ROOT / "results/exploratory_tradeoffs.json", report)
    print({policy: {key: row[key] for key in ("feasible_count", "candidate_count", "minimum_failures_per_aircraft_year")}
           for policy, row in report["development"]["policies"].items()})


if __name__ == "__main__":
    main()
