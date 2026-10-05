import numpy as np
import pandas as pd

from fleetsense.common import read_config


def measure(probabilities, labels):
    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels, dtype=float)
    if not len(labels):
        return {"count": 0, "brier": None, "ece": None, "reliability": []}
    order = np.argsort(probabilities, kind="stable")
    bins = np.array_split(order, min(read_config()["evaluation"]["reliability_bins"], len(order)))
    reliability = [{"count": len(group), "prediction": float(probabilities[group].mean()), "observed": float(labels[group].mean())}
                   for group in bins if len(group)]
    ece = sum(abs(row["prediction"] - row["observed"]) * row["count"] for row in reliability) / len(labels)
    return {"count": len(labels), "brier": float(np.mean((probabilities - labels)**2)), "ece": float(ece), "reliability": reliability}


def evaluate_calibration(tables, decisions, threshold):
    horizons = read_config()["forecast"]["horizons"]
    indexed = tables.set_index(["engine", "cycle"])
    valid = [(engine, cycle) for engine, cycle, *_ in decisions if cycle > 0]
    decision_table = indexed.loc[valid].reset_index() if valid else tables.iloc[:0]
    near_indices = [(engine, cycle) for engine, cycle, probability, *_ in decisions if cycle > 0 and probability >= threshold / 2]
    near_table = indexed.loc[near_indices].reset_index() if near_indices else tables.iloc[:0]
    output = {"all_cycles": [], "decision_points": [], "near_threshold": [], "subgroups": [],
              "decision_points_total": len(decisions), "cycle_zero_decisions": len(decisions) - len(valid)}
    for horizon in horizons:
        for key, frame in [("all_cycles", tables), ("decision_points", decision_table), ("near_threshold", near_table)]:
            output[key].append({"horizon": horizon, **measure(frame[f"p{horizon}"], frame.rul <= horizon)})
        for label, mask in [("FD001", tables.subset == "FD001"), ("FD003", tables.subset == "FD003"),
                            ("RUL ≤ 30", tables.rul <= 30), ("RUL 31–80", (tables.rul > 30) & (tables.rul <= 80)),
                            ("RUL > 80", tables.rul > 80)]:
            frame = tables.loc[mask]
            output["subgroups"].append({"horizon": horizon, "subgroup": label, **measure(frame[f"p{horizon}"], frame.rul <= horizon)})
    lead = read_config()["sim"]["lead_days"]
    output["used_horizons"] = sorted({next(horizon for horizon in horizons if horizon >= rate * lead)
                                       for rate in read_config()["sim"]["rates"]})
    return output


def missed_warnings(result, threshold):
    lead = read_config()["sim"]["lead_days"]
    histories = {}
    for _, _, risk, day, serial, _ in result["decisions"]:
        histories.setdefault(serial, {})[day] = risk
    missed = observed = insufficient = 0
    for event in result["events"]:
        if event["event"] != "failure":
            continue
        target = event["day"] - lead
        risk = histories.get(event["serial"], {}).get(target)
        if risk is None:
            insufficient += 1
        else:
            observed += 1
            missed += risk < threshold
    return {"missed": int(missed), "assessable": observed, "insufficient_history": insufficient}
