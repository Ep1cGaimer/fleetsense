import os

import numpy as np
import pandas as pd

from fleetsense.common import ROOT, read_config, read_json, write_json

COLUMNS = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{index}" for index in range(1, 22)]


def raw_paths():
    paths = {}
    for subset in read_config()["data"]["subsets"]:
        matches = sorted((ROOT / "data/raw").rglob(f"train_{subset}.txt"))
        if not matches:
            raise FileNotFoundError(f"Download required: train_{subset}.txt")
        paths[subset] = matches[0]
    return paths


def parse_file(path, subset):
    frame = pd.read_csv(path, sep=r"\s+", header=None)
    frame = frame.dropna(axis=1, how="all")
    if frame.shape[1] != len(COLUMNS):
        raise ValueError(f"Expected {len(COLUMNS)} columns, found {frame.shape[1]}")
    frame.columns = COLUMNS
    frame["engine"] = [f"{subset}-{unit:03d}" for unit in frame.unit]
    frame["subset"] = subset
    frame = frame.sort_values(["engine", "cycle"]).reset_index(drop=True)
    for _, group in frame.groupby("engine"):
        if not np.array_equal(group.cycle.to_numpy(), np.arange(1, len(group) + 1)):
            raise ValueError("Engine cycles must be contiguous from one")
    frame["rul"] = frame.groupby("engine").cycle.transform("max") - frame.cycle
    return frame


def create_splits():
    config = read_config()
    generator = np.random.default_rng(config["seed"])
    test, folds = [], [[] for _ in range(config["data"]["folds"])]
    for subset, path in raw_paths().items():
        units = pd.read_csv(path, sep=r"\s+", header=None, usecols=[0])[0].unique()
        identifiers = np.array([f"{subset}-{int(unit):03d}" for unit in sorted(units)])
        identifiers = generator.permutation(identifiers)
        count = config["data"]["test_per_subset"]
        test.extend(identifiers[:count].tolist())
        remaining = identifiers[count:]
        offset = 0 if subset == "FD001" else 2
        for index, identifier in enumerate(remaining):
            folds[(index + offset) % len(folds)].append(str(identifier))
    split = {"seed": config["seed"], "test": sorted(test), "folds": [sorted(fold) for fold in folds]}
    split["dev"] = sorted(identifier for fold in split["folds"] for identifier in fold)
    if set(split["test"]) & set(split["dev"]):
        raise AssertionError("Split overlap")
    write_json(ROOT / "data/splits.json", split)
    return split


def load_split(partition):
    if partition == "test" and os.environ.get("SIH_FINAL_EVAL") != "1":
        raise PermissionError("Test partition is locked; only run_final_eval.py unlocks it")
    if partition not in {"test", "dev"}:
        raise ValueError("Partition must be dev or test")
    split = read_json(ROOT / "data/splits.json")
    selected = set(split[partition])
    frames = [parse_file(path, subset) for subset, path in raw_paths().items()]
    frame = pd.concat(frames, ignore_index=True)
    return frame.loc[frame.engine.isin(selected)].reset_index(drop=True)
