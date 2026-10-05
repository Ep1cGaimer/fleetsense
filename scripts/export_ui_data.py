import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, assert_lock, read_config, read_json, write_json
from fleetsense.data import parse_file, raw_paths


def export(summary):
    assert_lock()
    if summary["evaluation_kind"] != "final_test":
        raise RuntimeError("Production UI exports require final test results")
    prefix = {"schema_version": 1, "run_id": summary["run_id"], "data_labels": summary["data_labels"]}
    output = ROOT / "results/ui"
    write_json(output / "summary.json", summary)
    config = read_config()
    write_json(output / "policies.json", {**prefix, "rates": config["sim"]["rates"], "ratios": config["sim"]["downtime_ratios"],
                                         "turnarounds": config["sim"]["turnarounds"], "cells": summary["cells"],
                                         "frontier": summary["frontier"], "metrics": summary["policy_metrics"],
                                         "losing_cells": summary["audits"]["sensitivity"]["losing_cells"]})
    write_json(output / "calibration.json", {**prefix, **summary["calibration"]})
    replay = read_json(ROOT / "artifacts/replay.json")
    write_json(output / "replay.json", {**prefix, "days": replay["days"], "events": [event for event in replay["events"] if event["event"] != "fly"],
                                       "scenario": {key: value for key, value in replay["scenario"].items() if key not in {"demand", "serials"}},
                                       "checker_violations": summary["checker_violations"],
                                       "play_days_per_second": config["presentation"]["ui_play_days_per_second"]})
    write_json(output / "audits.json", {**prefix, **summary["audits"], "manifest": summary["manifest"],
                                       "tests": summary["manifest"]["tests"], "checker_violations": summary["checker_violations"]})
    write_json(output / "claims.json", {**prefix, "claims": summary["claims"]})
    raw = pd.concat([parse_file(path, subset) for subset, path in raw_paths().items()], ignore_index=True)
    metadata = read_json(ROOT / "artifacts/final_metadata.json")
    sensor = metadata["sensors"][0]
    training = raw.loc[raw.engine.isin(metadata["train_ids"])]
    bands = training.groupby("cycle")[sensor].quantile([0.05, 0.95]).unstack()
    table = pd.read_parquet(ROOT / "artifacts/test_tables.parquet").set_index(["engine", "cycle"])
    latest = {}
    for day in replay["days"]:
        for aircraft in day["aircraft"]:
            latest[aircraft["serial"]] = aircraft
    evidence = []
    horizons = config["forecast"]["horizons"]
    for serial, aircraft in latest.items():
        trajectory = aircraft["trajectory"]
        cycle = aircraft["cycle"]
        history = raw.loc[(raw.engine == trajectory) & (raw.cycle <= cycle)]
        band = bands.loc[bands.index <= max(cycle, 1)]
        probabilities = [float(table.loc[(trajectory, cycle), f"p{horizon}"]) for horizon in horizons] if cycle else [0.0] * len(horizons)
        evidence.append({"serial": serial, "trajectory": trajectory, "cycle": cycle, "sensor": sensor,
                         "cycles": history.cycle.tolist(), "values": history[sensor].tolist(),
                         "horizons": horizons, "probabilities": probabilities,
                         "band": {"age": band.index.tolist(), "low": band[0.05].tolist(), "high": band[0.95].tolist()}})
    write_json(output / "engine.json", {**prefix, "label": "Evaluation-only model evidence, not a diagnosis", "engines": evidence})
    make_figures(summary)


def make_figures(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    destination = ROOT / "results/figures"
    destination.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, len(read_config()["sim"]["turnarounds"]), figsize=(12, 4), layout="constrained")
    for axis, turnaround in zip(axes, read_config()["sim"]["turnarounds"]):
        rates, ratios = read_config()["sim"]["rates"], read_config()["sim"]["downtime_ratios"]
        matrix = np.array([[next(row["delta_availability_pp"] for row in summary["cells"]
                                 if row["rate"] == rate and row["downtime_ratio"] == ratio and row["turnaround"] == turnaround)
                            for rate in rates] for ratio in ratios])
        bound = max(abs(matrix.min()), abs(matrix.max()), 0.01)
        image = axis.imshow(matrix, cmap="BrBG", vmin=-bound, vmax=bound)
        axis.set_xticks(range(len(rates)), rates)
        axis.set_yticks(range(len(ratios)), ratios)
        axis.set_title(f"Turnaround {turnaround} days")
        axis.set_xlabel("Cycles per aircraft-day")
        axis.set_ylabel("Unplanned / planned downtime")
        for row in range(len(ratios)):
            for column in range(len(rates)):
                axis.text(column, row, f"{matrix[row, column]:+.2f}", ha="center", va="center")
        figure.colorbar(image, ax=axis, label="Availability difference (pp)")
    figure.suptitle("Public simulated engine benchmark (NASA C-MAPSS)\nSynthetic fleet scenario")
    figure.savefig(destination / "availability_heatmap.png", dpi=160)
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 5), layout="constrained")
    for policy, color in [("HT", "#e69f00"), ("CT", "#56b4e9"), ("FC", "#009e73")]:
        rows = [row for row in summary["frontier"] if row["policy"] == policy]
        axis.plot([row["failures_per_aircraft_year"] for row in rows], [row["availability_pct"] for row in rows], ".-", label=policy, color=color)
    axis.set_xlabel("Unplanned failures per aircraft-year")
    axis.set_ylabel("Availability (%)")
    axis.legend()
    axis.set_title("Public simulated engine benchmark (NASA C-MAPSS)\nSynthetic fleet scenario — reporting-only frontier")
    figure.savefig(destination / "failure_availability_frontier.png", dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, len(summary["calibration"]["used_horizons"]), figsize=(12, 4), layout="constrained")
    for axis, horizon in zip(np.atleast_1d(axes), summary["calibration"]["used_horizons"]):
        row = next(row for row in summary["calibration"]["decision_points"] if row["horizon"] == horizon)
        axis.plot([0, 1], [0, 1], "--", color="gray")
        axis.plot([bin["prediction"] for bin in row["reliability"]], [bin["observed"] for bin in row["reliability"]], ".-", color="#009e73")
        axis.set_title(f"Decision horizon {horizon} cycles")
        axis.set_xlabel("Predicted probability")
        axis.set_ylabel("Observed frequency")
    figure.suptitle("Public simulated engine benchmark (NASA C-MAPSS)\nSynthetic fleet scenario — decision-point calibration")
    figure.savefig(destination / "decision_calibration.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    export(read_json(ROOT / "results/summary.json"))
