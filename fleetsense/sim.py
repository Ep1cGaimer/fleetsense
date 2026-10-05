import json
from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fleetsense.common import read_config
from fleetsense.planner import choose_starts
from fleetsense.policies import EngineView, request


class Tables:
    def __init__(self, frame):
        self.horizons = np.array(read_config()["forecast"]["horizons"])
        self.rows = {}
        self.failures = {}
        for engine, group in frame.groupby("engine", sort=True):
            group = group.sort_values("cycle")
            values = np.zeros((int(group.cycle.max()) + 1, len(self.horizons) + 1))
            values[0, 0] = 1.0
            values[group.cycle.to_numpy(), :] = group[["hi"] + [f"p{horizon}" for horizon in self.horizons]].to_numpy()
            self.rows[engine] = values
            self.failures[engine] = int(group.cycle.max())
        self.engine_ids = sorted(self.rows)


@dataclass(frozen=True)
class Cell:
    rate: float
    downtime_ratio: int
    turnaround: int

    @property
    def key(self):
        return f"r{self.rate:g}_u{self.downtime_ratio}_R{self.turnaround}"


def cells():
    config = read_config()["sim"]
    return [Cell(rate, ratio, turnaround) for rate in config["rates"]
            for ratio in config["downtime_ratios"] for turnaround in config["turnarounds"]]


def scenario_seed(cell, seed):
    return [read_config()["seed"], int(round(cell.rate * 10)), cell.downtime_ratio, cell.turnaround, seed]


def simulate(tables, pool, cell, seed, policy, parameter=None, aircraft=None, keep_days=False):
    config = read_config()["sim"]
    days = config["days"]
    count = aircraft or config["aircraft"]
    stock_count = int(np.ceil(config["spares"] * count / config["aircraft"]))
    capacity = int(np.ceil(config["capacity"] * count / config["aircraft"]))
    planned_duration = config["planned_downtime"]
    unplanned_duration = planned_duration * cell.downtime_ratio
    sequence = np.random.SeedSequence(scenario_seed(cell, seed))
    demand_rng, draw_rng, age_rng = [np.random.default_rng(child) for child in sequence.spawn(3)]
    demand = demand_rng.poisson(cell.rate, size=(days, count))
    age_fractions = age_rng.uniform(0, config["initial_age_max_fraction"], size=count)
    stream, position, reuse = list(draw_rng.permutation(pool)), 0, 0
    serials, serial_counter = {}, 0
    events, firewall, decisions, replay = [], [], [], []
    installed, stock, shop = [], deque(), []
    queued = {}
    flights = failures = planned = cap_events = 0
    wasted = []
    available_days = np.zeros(days, dtype=int)

    def event(day, airframe, serial, event_type, **detail):
        events.append({"day": day, "aircraft": airframe, "serial": serial, "event": event_type, "detail": detail})

    def new_engine(cycle_fraction=0):
        nonlocal position, reuse, stream, serial_counter
        if position >= len(stream):
            stream = list(draw_rng.permutation(pool))
            position = 0
            reuse += 1
        trajectory = str(stream[position])
        position += 1
        serial_counter += 1
        serial = f"E{serial_counter:05d}"
        cycle = int(np.floor(cycle_fraction * tables.failures[trajectory]))
        serials[serial] = trajectory
        return {"serial": serial, "trajectory": trajectory, "cycle": cycle, "state": "serviceable", "end": -1}

    for airframe in range(count):
        engine = new_engine(age_fractions[airframe])
        installed.append(engine)
        event(-1, airframe, engine["serial"], "init_installed", cycle=engine["cycle"])
    for _ in range(stock_count):
        engine = new_engine()
        stock.append(engine)
        event(-1, -1, engine["serial"], "init_stock", cycle=0)

    for day in range(days):
        returning = [entry for entry in shop if entry["return"] == day]
        for entry in returning:
            fresh = new_engine()
            stock.append(fresh)
            event(day, -1, entry["serial"], "shop_return", new_serial=fresh["serial"])
        shop = [entry for entry in shop if entry["return"] != day]
        for airframe, engine in enumerate(installed):
            if engine["state"] == "maintenance" and engine["end"] < day:
                engine["state"] = "serviceable"
                event(day, airframe, engine["serial"], "serviceable")

        for airframe, engine in enumerate(installed):
            if engine["state"] != "serviceable":
                continue
            trajectory, cycle = engine["trajectory"], engine["cycle"]
            if policy == "OR":
                remaining = tables.failures[trajectory] - cycle
                requested, urgency = remaining <= cell.rate * config["lead_days"], -remaining
            else:
                view = EngineView(engine["serial"], cycle, tables.rows[trajectory], tables.horizons, firewall)
                requested, urgency = request(policy, parameter, view, cell.rate, config["lead_days"])
                cap_events += view.cap_events
                if policy == "FC":
                    decisions.append((trajectory, cycle, urgency, day, engine["serial"], airframe))
            if requested and airframe not in queued:
                queued[airframe] = {"aircraft": airframe, "day": day, "urgency": urgency, "kind": "planned"}
                event(day, airframe, engine["serial"], "request", urgency=urgency)
            elif airframe in queued and queued[airframe]["kind"] == "planned":
                queued[airframe]["urgency"] = urgency

        unplanned_queue = [entry for entry in queued.values() if entry["kind"] == "unplanned"]
        planned_queue = [entry for entry in queued.values() if entry["kind"] == "planned"]
        for entry in choose_starts(unplanned_queue, planned_queue, capacity, len(stock)):
            airframe = entry["aircraft"]
            removed = installed[airframe]
            spare = stock.popleft()
            duration = unplanned_duration if entry["kind"] == "unplanned" else planned_duration
            spare["state"], spare["end"] = "maintenance", day + duration - 1
            installed[airframe] = spare
            remaining = tables.failures[removed["trajectory"]] - removed["cycle"]
            if entry["kind"] == "planned":
                planned += 1
                wasted.append(remaining)
            shop.append({"serial": removed["serial"], "return": day + cell.turnaround})
            event(day, airframe, spare["serial"], "start", removed=removed["serial"],
                  kind=entry["kind"], duration=duration, end=spare["end"],
                  removed_cycle=removed["cycle"], wasted_life=remaining if entry["kind"] == "planned" else None)
            del queued[airframe]

        day_frames = []
        for airframe, engine in enumerate(installed):
            cycle_before = engine["cycle"]
            if engine["state"] == "serviceable":
                limit = tables.failures[engine["trajectory"]]
                delivered = min(int(demand[day, airframe]), limit - cycle_before)
                engine["cycle"] += delivered
                flights += delivered
                if delivered:
                    event(day, airframe, engine["serial"], "fly", before=cycle_before, after=engine["cycle"], cycles=delivered)
                if engine["cycle"] >= limit:
                    engine["state"] = "AOG"
                    failures += 1
                    queued[airframe] = {"aircraft": airframe, "day": day, "urgency": 0, "kind": "unplanned"}
                    event(day, airframe, engine["serial"], "failure", cycle=engine["cycle"])
                else:
                    available_days[day] += 1
            if engine["state"] == "maintenance" and engine["end"] == day:
                event(day, airframe, engine["serial"], "complete")
            if keep_days:
                risk_index = min(int(np.searchsorted(tables.horizons, np.ceil(cell.rate * config["lead_days"]))), len(tables.horizons) - 1)
                risk = float(tables.rows[engine["trajectory"]][engine["cycle"], risk_index + 1])
                day_frames.append({"aircraft": airframe, "serial": engine["serial"], "trajectory": engine["trajectory"],
                                   "cycle": engine["cycle"], "status": engine["state"], "risk": risk})
        if keep_days:
            replay.append({"day": day, "aircraft": day_frames, "stock": len(stock), "in_shop": len(shop)})

    metrics = {"availability": float(available_days.sum() / (count * days)),
               "failures_per_aircraft_year": failures / count * 365 / days,
               "planned_per_aircraft_year": planned / count * 365 / days,
               "wasted_life_cycles": float(np.mean(wasted)) if wasted else None,
               "flying_delivered": flights / int(demand.sum()) if demand.sum() else 1.0,
               "reuse_events": reuse, "cap_events": cap_events, "failures": failures,
               "planned_removals": planned, "wasted_life_total": int(sum(wasted)),
               "cycles_flown": flights, "cycles_demanded": int(demand.sum()),
               "early_availability": float(available_days[:30].sum() / (count * min(30, days)))}
    scenario = {"cell": cell.__dict__, "seed": seed, "policy": policy, "parameter": parameter,
                "days": days, "aircraft": count, "spares": stock_count, "capacity": capacity,
                "planned_downtime": planned_duration, "unplanned_downtime": unplanned_duration,
                "turnaround": cell.turnaround, "serials": serials, "demand": demand.tolist()}
    return {"metrics": metrics, "events": events, "firewall": firewall,
            "decisions": decisions, "days": replay, "scenario": scenario}


def save_run(result, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(result["events"])
    frame["detail"] = frame.detail.map(lambda value: json.dumps(value, separators=(",", ":")))
    frame.to_parquet(str(destination) + ".events.parquet", index=False, compression="zstd")
    pd.DataFrame(result["firewall"], columns=["serial", "t_requested", "current_cycle"]).to_parquet(
        str(destination) + ".firewall.parquet", index=False, compression="zstd")
    destination.parent.joinpath(destination.name + ".scenario.json").write_text(json.dumps(result["scenario"], separators=(",", ":")), encoding="utf-8")
