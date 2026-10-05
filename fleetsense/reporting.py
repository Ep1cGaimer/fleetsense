import platform
import re
import subprocess

import numpy as np

from fleetsense.common import ROOT, git, read_config, read_json, sha256

CLAIM_ROWS = [
    ("Development tuning achieved the declared failure budget", "Deviation", "results/tuning.json: no HT, CT or FC candidate met the budget; all used the registered fewest-failures fallback. This is not availability maximisation under a feasible budget."),
    ("Forecast policy vs best simple policy: availability, failures, wasted life (public simulated benchmark, synthetic fleet)", "Measured", "primary; guardrails"),
    ("Calibration of failure risk at the horizons the policy uses (untouched test engines)", "Measured", "calibration"),
    ("Every schedule independently checked: no constraint violations", "Measured", "checker_violations"),
    ("No future information reaches a policy (poisoned-future test)", "Measured", "audits.poisoned_future"),
    ("Health history follows the engine serial across airframes", "Deviation", "Only lifecycle-instance removal and installation traces are demonstrated. Overhaul creates a new serial; physical-component continuity across overhaul or airframes is not established."),
    ("Read-only adapters to e-MMS and IMMOLS", "Proposed", "Subject to authorised interface specification"),
    ("Writing back work orders or spares demands", "Future", "Not implemented"),
    ("Validation on real fleet data", "Future", "Public simulated benchmark only"),
    ("Access control, audit logging, signed updates, pinned dependencies, backups", "Requirement", "Production requirements; not a security certification"),
    ("Identifying the physical fault behind a risk score", "Not established", "Evidence view shows model evidence only"),
]


def claims(summary):
    return [{"claim": claim, "status": f"Measured ({summary['run_id']})" if status == "Measured" else status,
             "evidence": evidence} for claim, status, evidence in CLAIM_ROWS]


def tuning_feasibility(tuning, budget):
    output = {}
    for policy in ("HT", "CT", "FC"):
        rows = [row for row in tuning["rows"] if row["policy"] == policy]
        count = sum(row["failures_per_aircraft_year"] <= budget for row in rows)
        output[policy] = {"candidate_count": len(rows), "feasible_count": count,
                          "minimum_failures_per_aircraft_year": min(row["failures_per_aircraft_year"] for row in rows),
                          "recorded_parameter": tuning["selected"][policy],
                          "selection_mode": "availability_within_budget" if count else "fewest_failures_fallback"}
    return output


def numeric_leaves(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from numeric_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from numeric_leaves(child)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield value


def allowed_numbers(value):
    tokens = set()
    for number in numeric_leaves(value):
        if not np.isfinite(number):
            continue
        tokens.add(str(number))
        tokens.add(f"{number:g}")
        for precision in range(5):
            tokens.add(f"{number:.{precision}f}")
            tokens.add(f"{number:+.{precision}f}")
            tokens.add(f"{number:,.{precision}f}")
    def strings(item):
        if isinstance(item, dict):
            for child in item.values():
                yield from strings(child)
        elif isinstance(item, list):
            for child in item:
                yield from strings(child)
        elif isinstance(item, str):
            yield item
    for text in strings(value):
        tokens.update(re.findall(r"[+-]?\d+(?:\.\d+)?", text))
    return sorted(tokens)


def manifest(started, wall_seconds, tests, run_id, config_hash, dataset_hashes):
    freeze = subprocess.check_output([str(ROOT / ".venv/Scripts/python.exe"), "-m", "pip", "freeze"], text=True)
    import hashlib
    return {"run_id": run_id, "evaluation_kind": "final_test", "git_commit": git("rev-parse", "HEAD"),
            "prereg_sha256": config_hash, "dataset_sha256": dataset_hashes, "splits_sha256": sha256(ROOT / "data/splits.json"),
            "seeds": {"split": read_config()["seed"], "scenario": read_config()["evaluation"]["seeds"],
                      "bootstrap": read_config()["evaluation"]["bootstrap_seed"]},
            "pip_freeze_sha256": hashlib.sha256(freeze.encode()).hexdigest(), "requirements_lock_sha256": sha256(ROOT / "requirements.lock"),
            "os": platform.platform(), "cpu": platform.processor(), "logical_cpus": __import__("os").cpu_count(),
            "gpu": "not used; CPU-only experiment", "python": platform.python_version(), "started_utc": started,
            "wall_seconds": wall_seconds, "tests": tests}


def presentation(summary):
    config = read_config()
    primary = summary["primary"]
    lower, upper = primary["ci95_pp"]
    metrics = [
        {"label": "Availability difference", "value": f"{primary['delta_availability_pp']:+.2f} pp", "source": "$.primary.delta_availability_pp"},
        {"label": "Interval", "value": f"{lower:+.2f} to {upper:+.2f} pp", "source": "$.primary.ci95_pp"},
        {"label": "Paired scenarios", "value": summary["counts"]["paired_scenarios"], "source": "$.counts.paired_scenarios"},
        {"label": "Tests passed (includes UI)", "value": summary["tests_passed"], "source": "$.tests_passed"},
        {"label": "Checker violations", "value": summary["checker_violations"], "source": "$.checker_violations"},
        {"label": "Hierarchical resamples", "value": primary["bootstrap_replicates"], "source": "$.primary.bootstrap_replicates"},
        {"label": "Evaluation wall time", "value": f"{summary['wall_seconds']:.1f} s", "source": "$.wall_seconds"},
        {"label": "Mutation checks", "value": f"{summary['counts']['checker_mutations_caught']}/{summary['counts']['checker_mutations_total']}", "source": "$.counts"},
    ]
    constants = {"prereg": config, "slide_ordinals": list(range(1, config["presentation"]["slide_count"] + 1)),
                 "reference_years": [2008, 2021, 2017, 2002, 2019], "confidence_percent": config["evaluation"]["confidence"] * 100,
                 "python_version": platform.python_version()}
    tuning = read_json(ROOT / "results/tuning.json")
    feasibility = tuning_feasibility(tuning, config["tuning"]["failure_budget"])
    feasibility_text = "; ".join(f"{policy}: {row['feasible_count']}/{row['candidate_count']} feasible" for policy, row in feasibility.items())
    fallback_policies = ", ".join(policy for policy, row in feasibility.items() if row["feasible_count"] == 0)
    tuning_fact = (f"Development failure budget {config['tuning']['failure_budget']:g} per aircraft-year: {feasibility_text}. "
                   + (f"Registered fewest-failures fallback used for {fallback_policies}." if fallback_policies else "All policies had feasible candidates."))
    return {"headline": summary["verdict_text"], "metrics": metrics,
            "facts": [tuning_fact,
                      "Thresholds were frozen from development results; test-frontier points are reporting-only, not new policy selections.",
                      f"{summary['counts']['engines']} run-to-failure engines: {summary['counts']['dev_engines']} development, {summary['counts']['test_engines']} held-out test.",
                      f"{summary['counts']['cells']} operating cells and {len(config['evaluation']['seeds'])} common seeds; best simple rule is {summary['best_simple']}.",
                      f"Calibrated risk at {summary['counts']['horizons']} horizons; training, calibration and evaluation engines are disjoint.",
                      "Independent resource, duration, serial, failure-boundary and information-firewall checks.",
                      "All thresholds selected globally on development simulations, not test outcomes."],
            "limitations": ["No development candidate met the failure budget in any policy grid. The comparison uses fewest-failures fallbacks, not availability-optimal policies under a feasible budget; relative final guardrails do not establish absolute budget compliance.",
                            "REFUTED applies to the frozen policies and tested scenario range, not to forecasting in general. No test retuning or replacement final policy is justified by the exploratory frontier.",
                            "Exploratory Pareto points describe aggregate availability, failures and wasted-life tradeoffs only; they have no new uncertainty estimates or confirmatory status. Test engines are held out for selection but also used in the registered reporting-only frontier.",
                            "Public simulated engine benchmark and synthetic single-engine fleet; not evidence for operational fleets.",
                            "Overhaul is modelled as a new trajectory; spares, demand and turnaround are declared assumptions.",
                            "Model evidence is not a physical diagnosis. Authorised e-MMS and IMMOLS adapters are proposed.",
                            "Access control, signed updates and deployment assurance remain requirements."],
            "tuning_feasibility": {"failure_budget": config["tuning"]["failure_budget"], "policies": feasibility},
            "stack": [f"Python {platform.python_version()}", "pandas", "LightGBM", "scikit-learn", "NumPy/SciPy", "FastAPI", "HTML/CSS/JS", "offline Plotly", "pytest"],
            "data_boundary": [f"Dev: {summary['counts']['dev_engines']} engines in {summary['counts']['folds']} engine-disjoint folds.",
                              f"Final training: {len(read_json(ROOT / 'data/splits.json')['folds'][0]) * 3} engines; calibration: {len(read_json(ROOT / 'data/splits.json')['folds'][3])}.",
                              f"Test: {summary['counts']['test_engines']} engines, unlocked only by the final entry point."],
            "allowed_constants": list(numeric_leaves(constants)) + [platform.python_version(), summary["problem_id"]],
            "constants": constants, "counts": summary["counts"], "data_labels": summary["data_labels"],
            "guardrail_wording": "No failure-increase statement unless observed difference and upper CI are nonpositive.",
            "verdict_templates": {"SUPPORTED": "On a public simulated engine benchmark, calibrated forecasting raised fleet availability by {dA:.1f} pp (95% CI {lo:.1f} to {hi:.1f}) over the best tuned simple rule, with all declared guardrails met.",
                                  "INCONCLUSIVE": "Forecasting changed availability by {dA:+.1f} pp (95% CI {lo:+.1f} to {hi:+.1f}): not enough evidence yet to justify it. FleetSense shows this before money is spent.",
                                  "REFUTED": "Within the tested range, forecasting did not reach a worthwhile gain (upper 95% CI {hi:+.1f} pp < {minimum:.1f} pp). FleetSense caught this before deployment."}}
