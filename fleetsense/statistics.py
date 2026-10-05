import numpy as np

from fleetsense.common import read_config


def aggregate(metrics):
    planned = sum(row["planned_removals"] for row in metrics)
    output = {key: float(np.mean([row[key] for row in metrics])) for key in
              ["availability", "failures_per_aircraft_year", "planned_per_aircraft_year", "flying_delivered", "early_availability"]}
    output["availability_pct"] = output["availability"] * 100
    output["wasted_life_cycles"] = sum(row["wasted_life_total"] for row in metrics) / planned if planned else None
    output["reuse_events"] = sum(row["reuse_events"] for row in metrics)
    output["cap_events"] = sum(row["cap_events"] for row in metrics)
    return output


def contrast(forecast, baseline):
    waste = forecast["wasted_life_cycles"]
    base_waste = baseline["wasted_life_cycles"]
    return {"delta_availability_pp": (forecast["availability"] - baseline["availability"]) * 100,
            "delta_failures": forecast["failures_per_aircraft_year"] - baseline["failures_per_aircraft_year"],
            "waste_ratio": waste / base_waste if waste is not None and base_waste is not None and base_waste > 0 else None,
            "delta_flying_pp": (forecast["flying_delivered"] - baseline["flying_delivered"]) * 100}


def percentile(values):
    if any(value is None or not np.isfinite(value) for value in values):
        return [None, None]
    confidence = read_config()["evaluation"]["confidence"]
    return np.quantile(values, [(1 - confidence) / 2, (1 + confidence) / 2]).tolist()


def verdict(primary, guardrails):
    lower, upper = primary["ci95_pp"]
    minimum = primary["minimum_gain_pp"]
    if lower > 0 and primary["delta_availability_pp"] >= minimum and all(row["met"] for row in guardrails.values()):
        return "SUPPORTED"
    if upper < minimum:
        return "REFUTED"
    return "INCONCLUSIVE"


def verdict_text(outcome, primary, failures):
    delta = primary["delta_availability_pp"]
    lower, upper = primary["ci95_pp"]
    if outcome == "SUPPORTED":
        qualifier = "with no more unplanned failures" if failures["delta"] <= 0 and failures["ci95"][1] <= 0 else "with all declared guardrails met"
        return (f"On a public simulated engine benchmark, calibrated forecasting raised fleet availability by {delta:.1f} pp "
                f"(95% CI {lower:.1f} to {upper:.1f}) over the best tuned simple rule, {qualifier}.")
    if outcome == "REFUTED":
        return (f"Within the tested range, forecasting did not reach a worthwhile gain (upper 95% CI {upper:+.1f} pp "
                f"< {primary['minimum_gain_pp']:.1f} pp). FleetSense caught this before deployment.")
    return (f"Forecasting changed availability by {delta:+.1f} pp (95% CI {lower:+.1f} to {upper:+.1f}): "
            "not enough evidence yet to justify it. FleetSense shows this before money is spent.")


def select_parameter(rows, budget):
    feasible = [row for row in rows if row["failures_per_aircraft_year"] <= budget]
    if feasible:
        return max(feasible, key=lambda row: (row["availability"], -row["failures_per_aircraft_year"], -row["parameter"]))
    return min(rows, key=lambda row: (row["failures_per_aircraft_year"], -row["availability"], row["parameter"]))
