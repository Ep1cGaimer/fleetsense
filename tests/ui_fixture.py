from fleetsense.common import read_config, write_json


def synthetic_ui_fixture(directory):
    labels = ["synthetic UI test fixture — not final evaluation"]
    prefix = {"schema_version": 1, "run_id": "synthetic-ui-smoke", "data_labels": labels}
    metric = {"availability": 0.9, "availability_pct": 90, "failures_per_aircraft_year": 0.1,
              "planned_per_aircraft_year": 1, "wasted_life_cycles": 20, "flying_delivered": 0.9}
    guards = {"failures": {"delta": 0, "ci95": [-0.01, 0.01], "limit": 0.05, "met": True},
              "wasted_life": {"ratio": 1, "ci95": [0.9, 1.1], "limit": 1.1, "met": True},
              "flying_delivered": {"delta_pp": 0, "ci95_pp": [-1, 1], "limit_pp": -0.5, "met": True}}
    summary = {**prefix, "verdict": "INCONCLUSIVE", "verdict_text": "Synthetic routing fixture, not final evaluation evidence.",
               "best_simple": "CT", "primary": {"delta_availability_pp": 0, "ci95_pp": [-1, 1], "minimum_gain_pp": 1, "bootstrap_replicates": 2},
               "counts": {"paired_scenarios": 2}, "guardrails": guards,
               "presentation": {"limitations": ["Synthetic UI fixture only"]}}
    write_json(directory / "summary.json", summary)
    config = read_config()
    cells = [{"rate": rate, "downtime_ratio": ratio, "turnaround": turnaround, "delta_availability_pp": 0, "ci95_pp": [-1, 1]}
             for rate in config["sim"]["rates"] for ratio in config["sim"]["downtime_ratios"] for turnaround in config["sim"]["turnarounds"]]
    write_json(directory / "policies.json", {**prefix, "rates": config["sim"]["rates"], "ratios": config["sim"]["downtime_ratios"],
                                            "turnarounds": config["sim"]["turnarounds"], "cells": cells,
                                            "metrics": {policy: metric for policy in ("HT", "CT", "FC", "OR")},
                                            "frontier": [{"policy": policy, "parameter": 1, **metric} for policy in ("HT", "CT", "FC")], "losing_cells": []})
    row = {"horizon": 20, "count": 2, "brier": 0.1, "ece": 0.1, "reliability": [{"count": 2, "prediction": 0.2, "observed": 0.3}]}
    write_json(directory / "calibration.json", {**prefix, "used_horizons": [20], "all_cycles": [row], "decision_points": [row],
                                               "near_threshold": [row], "subgroups": [{**row, "subgroup": "synthetic"}],
                                               "cycle_zero_decisions": 1, "missed_warnings": {"missed": 0, "assessable": 1, "insufficient_history": 0}})
    write_json(directory / "replay.json", {**prefix, "days": [{"day": 0, "stock": 1, "in_shop": 0, "aircraft": [{"aircraft": 0, "serial": "E00001", "trajectory": "synthetic", "cycle": 1, "status": "serviceable", "risk": 0.2}]}],
                                          "events": [], "scenario": {"aircraft": 1}, "checker_violations": 0, "play_days_per_second": 10})
    write_json(directory / "audits.json", {**prefix, "leakage": {"disjointness_passed": True, "label": "Synthetic fixture", "contrast": [{"horizon": 20, "honest_brier": 0.1, "leaked_brier": 0.05}]},
                                          "poisoned_future": {"passed": True}, "mutations": {"caught": 8, "total": 8}, "checker_violations": 0,
                                          "tests": {"passed": 1, "failed": 0}, "scale": [{"aircraft": 12, "capacity": 1, "spares": 3, "seconds_per_simulated_day": 0.1, "passed": True}],
                                          "horizon": {"first_days": 30, "early_delta_availability_pp": 0, "full_delta_availability_pp": 0}, "optional_p2": "Synthetic fixture", "manifest": {"evaluation_kind": "synthetic_ui_smoke"}})
    write_json(directory / "claims.json", {**prefix, "claims": [{"claim": "Synthetic fixture", "status": "Demonstrated (synthetic)", "evidence": "Routing test only"}]})
    write_json(directory / "engine.json", {**prefix, "engines": [{"serial": "E00001", "trajectory": "synthetic", "cycle": 1, "sensor": "s2", "cycles": [1], "values": [1],
                                                                "horizons": [10, 20], "probabilities": [0.1, 0.2], "band": {"age": [1], "low": [0.5], "high": [1.5]}}]})
