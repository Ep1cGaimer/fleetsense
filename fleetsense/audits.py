import time

import numpy as np
import pandas as pd

from fleetsense.calibration import measure
from fleetsense.checker import check
from fleetsense.common import ROOT, read_config, read_json
from fleetsense.data import load_split
from fleetsense.features import features, sensor_list
from fleetsense.forecast import Forecast
from fleetsense.sim import Cell, Tables, simulate


def leakage_audit(test_table, final_metadata):
    oof = read_json(ROOT / "artifacts/oof_metadata.json")
    for item in oof + [final_metadata]:
        assert not set(item["train_ids"]) & set(item["calibration_ids"])
        assert not set(item["evaluation_ids"]) & (set(item["train_ids"]) | set(item["calibration_ids"]))
    dev, test = load_split("dev"), load_split("test")
    split = read_json(ROOT / "data/splits.json")
    leak_training = pd.concat([dev.loc[dev.engine.isin(final_metadata["train_ids"])], test], ignore_index=True)
    sensors = sensor_list(leak_training)
    train_features = features(leak_training, sensors)
    calibration = features(dev.loc[dev.engine.isin(split["folds"][3])], sensors)
    evaluation = features(test, sensors)
    model = Forecast().fit(train_features, calibration)
    leaked_probabilities = model.predict(evaluation, enforce_disjoint=False)
    rows = []
    for position, horizon in enumerate(model.horizons):
        honest = measure(test_table[f"p{horizon}"], test_table.rul <= horizon)["brier"]
        leaked = measure(leaked_probabilities[:, position], evaluation.rul <= horizon)["brier"]
        rows.append({"horizon": horizon, "honest_brier": honest, "leaked_brier": leaked,
                     "leaked_minus_honest": leaked - honest})
    return {"disjointness_passed": True, "fitted_objects": len(oof) + 1,
            "contrast": rows, "contrast_train_ids": model.train_ids,
            "label": "Deliberately contaminated audit model; never used for decisions. Lower Brier is better; direction is observed, not assumed."}


def scale_audit(test_table, failures, parameter):
    tables = Tables(test_table)
    rows = []
    cell = Cell(1.0, 4, 45)
    for count in read_config()["evaluation"]["scale_aircraft"]:
        started = time.perf_counter()
        result = simulate(tables, tables.engine_ids, cell, 0, "FC", parameter, aircraft=count)
        simulation_seconds = time.perf_counter() - started
        checked = time.perf_counter()
        violations = check(result["events"], result["scenario"], failures, result["firewall"])
        if violations:
            raise RuntimeError(violations[:5])
        rows.append({"aircraft": count, "wall_seconds": simulation_seconds,
                     "seconds_per_simulated_day": simulation_seconds / read_config()["sim"]["days"],
                     "checker_seconds": time.perf_counter() - checked,
                     "capacity": result["scenario"]["capacity"], "spares": result["scenario"]["spares"],
                     "passed": simulation_seconds / read_config()["sim"]["days"] < read_config()["evaluation"]["scale_seconds_per_day_limit"]})
    return rows
