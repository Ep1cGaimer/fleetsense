import copy
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fleetsense import checker
from fleetsense.common import ROOT, read_config, read_json
from fleetsense.data import load_split
from fleetsense.features import features, sensor_list
from fleetsense.planner import choose_starts
from fleetsense.policies import EngineView, request
from fleetsense.sim import Cell, Tables, simulate
from fleetsense.statistics import select_parameter, verdict, verdict_text


def fake_table():
    config = read_config()
    frames = []
    for index in range(1, 8):
        length = 40 + index * 3
        cycles = np.arange(1, length + 1)
        frame = pd.DataFrame({"engine": f"FD001-{index:03d}", "cycle": cycles,
                              "hi": 1 - cycles / length, "rul": length - cycles, "subset": "FD001"})
        for horizon in config["forecast"]["horizons"]:
            frame[f"p{horizon}"] = np.clip((cycles + horizon - length) / max(horizon, 1), 0, 1)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def sample_raw():
    generator = np.random.default_rng(read_config()["seed"])
    rows = []
    for engine in range(2):
        for cycle in range(1, 41):
            rows.append({"engine": f"FD001-{engine:03d}", "cycle": cycle, "rul": 40 - cycle,
                         "subset": "FD001", "s2": generator.normal() + cycle, "s3": generator.normal(),
                         "s1": 1.0, "s5": float(cycle % 2), "op1": generator.normal()})
    return pd.DataFrame(rows)


def test_test_lock(monkeypatch):
    monkeypatch.delenv("SIH_FINAL_EVAL", raising=False)
    with pytest.raises(PermissionError):
        load_split("test")


def test_only_final_entry_sets_unlock():
    for path in list((ROOT / "fleetsense").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        if path.name != "run_final_eval.py":
            assert 'os.environ["SIH_FINAL_EVAL"] =' not in path.read_text(encoding="utf-8")


def test_split_disjointness():
    split = read_json(ROOT / "data/splits.json")
    assert not set(split["dev"]) & set(split["test"])
    assert len(split["test"]) == 60
    assert len(split["dev"]) == 140
    assert [len(fold) for fold in split["folds"]] == [35] * 4
    for index, fold in enumerate(split["folds"]):
        other = [identifier for position, group in enumerate(split["folds"]) if position != index for identifier in group]
        assert not set(fold) & set(other)


def test_training_only_sensor_filter():
    raw = sample_raw()
    assert sensor_list(raw) == ["s2", "s3"]
    assert not any(name.startswith("op") for name in sensor_list(raw))


@pytest.mark.parametrize("trial", range(20))
def test_feature_prefix_invariance(trial):
    raw = sample_raw()
    generator = np.random.default_rng(read_config()["seed"] + trial)
    engine = generator.choice(raw.engine.unique())
    cycle = int(generator.integers(1, 41))
    trajectory = raw.loc[raw.engine == engine]
    full = features(trajectory, ["s2", "s3"])
    prefix = features(trajectory.loc[trajectory.cycle <= cycle], ["s2", "s3"])
    pd.testing.assert_series_equal(full.loc[full.cycle == cycle].iloc[0], prefix.iloc[-1], check_names=False)


def test_probability_monotonicity():
    values = np.array([[0.5, 0.2, 0.8, 0.4]])
    monotone = np.maximum.accumulate(values, axis=1)
    assert np.all(np.diff(monotone, axis=1) >= 0)
    path = ROOT / "artifacts/oof_tables.parquet"
    if path.exists():
        frame = pd.read_parquet(path)
        assert np.all(np.diff(frame[[f"p{horizon}" for horizon in read_config()["forecast"]["horizons"]]].to_numpy(), axis=1) >= 0)


@pytest.mark.parametrize("policy,parameter", [("HT", 110), ("CT", 0.2), ("FC", 0.2)])
def test_poisoned_future(policy, parameter):
    tables = Tables(fake_table())
    identifier = tables.engine_ids[0]
    original = tables.rows[identifier]
    for cycle in [0, 5, 20, 35]:
        poisoned = original.copy()
        poisoned[cycle + 1:] = np.nan
        first = request(policy, parameter, EngineView("serial", cycle, original, tables.horizons, []), 1.0, 14)
        second = request(policy, parameter, EngineView("serial", cycle, poisoned, tables.horizons, []), 1.0, 14)
        assert first == second


def test_query_grid_and_cap():
    tables = Tables(fake_table())
    log = []
    view = EngineView("serial", 20, tables.rows[tables.engine_ids[0]], tables.horizons, log)
    assert len(view._rows) == view.current_cycle + 1
    assert not view._rows.flags.writeable
    assert view.risk(14) == view.row()[2]
    assert view.risk(101) == view.row()[-1]
    assert view.cap_events == 1
    with pytest.raises(PermissionError):
        view.row(21)


def test_planner_known_answer():
    unplanned = [{"aircraft": 1, "day": 3, "urgency": 0, "kind": "unplanned"}]
    planned = [{"aircraft": 0, "day": 1, "urgency": 0.9, "kind": "planned"}]
    assert choose_starts(unplanned, planned, 1, 1) == unplanned
    assert choose_starts(unplanned, planned, 2, 1) == unplanned
    assert choose_starts(unplanned, planned, 2, 0) == []
    assert choose_starts([], planned, 1, 1) == planned


def known_events():
    scenario = {"aircraft": 2, "spares": 1, "capacity": 1, "planned_downtime": 2,
                "unplanned_downtime": 4, "turnaround": 20, "days": 6,
                "serials": {"A": "a", "B": "b", "S": "s"}, "demand": [[1, 1]] * 6}
    events = [
        {"day": -1, "aircraft": 0, "serial": "A", "event": "init_installed", "detail": {"cycle": 0}},
        {"day": -1, "aircraft": 1, "serial": "B", "event": "init_installed", "detail": {"cycle": 0}},
        {"day": -1, "aircraft": -1, "serial": "S", "event": "init_stock", "detail": {"cycle": 0}},
        {"day": 0, "aircraft": 0, "serial": "S", "event": "start", "detail": {"removed": "A", "kind": "planned", "duration": 2, "end": 1, "wasted_life": 100}},
        {"day": 1, "aircraft": 0, "serial": "S", "event": "complete", "detail": {}},
        {"day": 2, "aircraft": 0, "serial": "S", "event": "serviceable", "detail": {}},
        {"day": 2, "aircraft": 0, "serial": "S", "event": "fly", "detail": {"before": 0, "after": 1, "cycles": 1}},
    ]
    return events, scenario, {"a": 100, "b": 100, "s": 100}, []


def test_known_two_aircraft_checker():
    assert checker.check(*known_events()) == []


@pytest.mark.parametrize("mutation", ["capacity", "conservation", "grounded_flight", "failure_boundary", "spare", "duration", "serial_unique", "future_access"])
def test_checker_mutations(mutation):
    events, scenario, failures, firewall = copy.deepcopy(known_events())
    if mutation == "capacity":
        scenario["capacity"] = 0
    elif mutation == "conservation":
        scenario["spares"] = 2
    elif mutation == "grounded_flight":
        events.insert(4, {"day": 0, "aircraft": 0, "serial": "S", "event": "fly", "detail": {"before": 0, "after": 1, "cycles": 1}})
    elif mutation == "failure_boundary":
        failures["s"] = 0
    elif mutation == "spare":
        events[2]["serial"] = "X"
    elif mutation == "duration":
        events[3]["detail"]["duration"] = 3
    elif mutation == "serial_unique":
        events[1]["serial"] = "A"
    elif mutation == "future_access":
        firewall.append(("S", 2, 1))
    assert mutation in {entry["code"] for entry in checker.check(events, scenario, failures, firewall)}


def test_checker_independent():
    source = inspect.getsource(checker)
    assert "import sim" not in source
    assert "import planner" not in source


def test_simulator_checked_and_common_demand():
    tables = Tables(fake_table())
    first = simulate(tables, tables.engine_ids, Cell(1.0, 4, 45), 0, "HT", 35, aircraft=2, keep_days=True)
    second = simulate(tables, tables.engine_ids, Cell(1.0, 4, 45), 0, "FC", 0.2, aircraft=2)
    assert first["scenario"]["demand"] == second["scenario"]["demand"]
    assert checker.check(first["events"], first["scenario"], tables.failures, first["firewall"]) == []
    assert checker.check(second["events"], second["scenario"], tables.failures, second["firewall"]) == []
    assert len(first["days"]) == 365


def test_fitted_engine_disjointness():
    path = ROOT / "artifacts/oof_metadata.json"
    if path.exists():
        for item in read_json(path):
            assert not set(item["train_ids"]) & set(item["calibration_ids"])
            assert not set(item["evaluation_ids"]) & (set(item["train_ids"]) | set(item["calibration_ids"]))
            assert item["health_train_ids"] == item["scaler_train_ids"] == item["train_ids"]


@pytest.mark.parametrize("policy,parameter", [("CT", 0.2), ("FC", 0.2)])
def test_daily_simulation_poisoned_future(monkeypatch, policy, parameter):
    import fleetsense.sim as simulator
    tables = Tables(fake_table())
    first = simulate(tables, tables.engine_ids, Cell(1.0, 4, 45), 0, policy, parameter, aircraft=2)
    original_view = EngineView

    def poisoned_view(serial, current, rows, horizons, log):
        poisoned = rows.copy()
        poisoned[current + 1:] = np.nan
        return original_view(serial, current, poisoned, horizons, log)

    monkeypatch.setattr(simulator, "EngineView", poisoned_view)
    second = simulate(tables, tables.engine_ids, Cell(1.0, 4, 45), 0, policy, parameter, aircraft=2)
    assert first["events"] == second["events"]
    assert first["metrics"] == second["metrics"]
    assert first["decisions"] == second["decisions"]


@pytest.mark.parametrize("missing", ["complete", "serviceable"])
def test_checker_missing_lifecycle(missing):
    events, scenario, failures, firewall = known_events()
    events = [event for event in events if event["event"] != missing]
    assert checker.check(events, scenario, failures, firewall)


def test_checker_rejects_negative_flight():
    events, scenario, failures, firewall = copy.deepcopy(known_events())
    events[-1]["detail"] = {"before": 0, "after": -1, "cycles": -1}
    assert "cycles" in {row["code"] for row in checker.check(events, scenario, failures, firewall)}


def test_checker_requires_failure_event():
    events, scenario, failures, firewall = copy.deepcopy(known_events())
    failures["s"] = 1
    events.append({"day": 3, "aircraft": 0, "serial": "S", "event": "request", "detail": {"urgency": 1}})
    assert "failure_boundary" in {row["code"] for row in checker.check(events, scenario, failures, firewall)}


def test_checker_requires_failure_before_planned_start():
    events, scenario, failures, firewall = copy.deepcopy(known_events())
    failures["b"] = 1
    events.insert(3, {"day": 0, "aircraft": 1, "serial": "B", "event": "fly", "detail": {"before": 0, "after": 1, "cycles": 1}})
    events[4]["aircraft"] = 1
    events[4]["detail"]["removed"] = "B"
    events[4]["detail"]["wasted_life"] = 0
    assert "failure_boundary" in {row["code"] for row in checker.check(events, scenario, failures, firewall)}


def test_tuning_budget():
    rows = [{"parameter": 1, "availability": 0.99, "failures_per_aircraft_year": 0.2},
            {"parameter": 2, "availability": 0.9, "failures_per_aircraft_year": 0.05}]
    assert select_parameter(rows, 0.1)["parameter"] == 2
    assert select_parameter(rows, 0.01)["parameter"] == 2


@pytest.mark.parametrize("point,interval,met,expected", [(2, [1, 3], True, "SUPPORTED"),
                                                       (0.2, [-0.1, 0.8], True, "REFUTED"),
                                                       (0.8, [-0.1, 1.8], True, "INCONCLUSIVE"),
                                                       (2, [1, 3], False, "INCONCLUSIVE")])
def test_verdict(point, interval, met, expected):
    primary = {"delta_availability_pp": point, "ci95_pp": interval, "minimum_gain_pp": 1.0}
    assert verdict(primary, {"guardrail": {"met": met}}) == expected


def test_supported_wording_honest():
    primary = {"delta_availability_pp": 2, "ci95_pp": [1, 3], "minimum_gain_pp": 1.0}
    assert "no more" not in verdict_text("SUPPORTED", primary, {"delta": 0.01, "ci95": [-0.01, 0.03]})


def test_banned_user_facing_words():
    banned = ["proves", "guarantees", "compliant", "fraud", "ghost", "novel architecture", "real data"]
    paths = [ROOT / "README.md"] + list((ROOT / "app/ui").glob("*.html")) + list((ROOT / "app/ui").glob("*.js"))
    paths += list((ROOT / "submission").glob("*.md"))
    for path in paths:
        if path.exists():
            text = path.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in text, f"{word}: {path}"
