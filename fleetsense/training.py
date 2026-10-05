import pickle

import pandas as pd

from fleetsense.common import ROOT, read_config, read_json, write_json
from fleetsense.data import load_split
from fleetsense.features import features, sensor_list
from fleetsense.forecast import Forecast
from fleetsense.health_index import HealthIndex


def build_table(raw, train_ids, calibration_ids, evaluation_ids, tag):
    training_raw = raw.loc[raw.engine.isin(train_ids)]
    sensors = sensor_list(training_raw)
    frame = features(raw, sensors)
    training = frame.loc[frame.engine.isin(train_ids)]
    calibration = frame.loc[frame.engine.isin(calibration_ids)]
    evaluation = frame.loc[frame.engine.isin(evaluation_ids)]
    forecast = Forecast().fit(training, calibration)
    health = HealthIndex().fit(training, sensors)
    probabilities = forecast.predict(evaluation)
    table = evaluation[["engine", "cycle", "rul", "subset"]].copy()
    table["hi"] = health.predict(evaluation)
    for position, horizon in enumerate(forecast.horizons):
        table[f"p{horizon}"] = probabilities[:, position]
    metadata = {"tag": tag, "train_ids": train_ids, "calibration_ids": calibration_ids,
                "evaluation_ids": evaluation_ids, "sensors": sensors, "scaler_train_ids": train_ids,
                "health_train_ids": train_ids}
    (ROOT / "artifacts").mkdir(exist_ok=True)
    with (ROOT / "artifacts" / f"{tag}.pkl").open("wb") as output:
        pickle.dump({"forecast": forecast, "health": health, "metadata": metadata}, output)
    return table, metadata


def build_oof():
    split = read_json(ROOT / "data/splits.json")
    raw = load_split("dev")
    tables, metadata = [], []
    for fold in range(4):
        train_ids = sorted(split["folds"][(fold + 2) % 4] + split["folds"][(fold + 3) % 4])
        table, audit = build_table(raw, train_ids, split["folds"][(fold + 1) % 4], split["folds"][fold], f"fold{fold}")
        tables.append(table)
        metadata.append(audit)
        print(f"OOF fold {fold} complete", flush=True)
    table = pd.concat(tables, ignore_index=True)
    table.to_parquet(ROOT / "artifacts/oof_tables.parquet", index=False)
    write_json(ROOT / "artifacts/oof_metadata.json", metadata)
    write_json(ROOT / "results/sensor_list.json", {item["tag"]: item["sensors"] for item in metadata})
    expected = read_config()["data"]["expected_sensors"]
    differences = [item for item in metadata if item["sensors"] != expected]
    with (ROOT / "DECISIONS.md").open("a", encoding="utf-8") as output:
        output.write("\n## Observed training-only sensor selection\n\n")
        for item in metadata:
            output.write(f"- {item['tag']}: {', '.join(item['sensors'])}.\n")
        output.write("\nActual lists are used; " + ("differences from the expected list exist." if differences else "all match the expected list.") + "\n")
    return table


def build_final():
    split = read_json(ROOT / "data/splits.json")
    raw = pd.concat([load_split("dev"), load_split("test")], ignore_index=True)
    train_ids = sorted(identifier for fold in split["folds"][:3] for identifier in fold)
    table, metadata = build_table(raw, train_ids, split["folds"][3], split["test"], "final")
    table.to_parquet(ROOT / "artifacts/test_tables.parquet", index=False)
    write_json(ROOT / "artifacts/final_metadata.json", metadata)
    return table, metadata
