import json
from collections import defaultdict


def check(events, scenario, failure_cycles, firewall):
    violations = []
    stock, shop, installed, cycles, states, maintenance = set(), {}, {}, {}, {}, {}
    starts = defaultdict(int)
    last_day = None
    completions = set()
    pending_failure = None

    def flag(code, day, detail):
        violations.append({"code": code, "day": day, "detail": detail})

    def conserve(day):
        inventory = stock | set(shop) | set(installed.values())
        if len(stock) + len(shop) + len(installed) != scenario["aircraft"] + scenario["spares"]:
            flag("conservation", day, "Inventory count changed")
        if len(inventory) != len(stock) + len(shop) + len(installed):
            flag("serial_unique", day, "Serial appears in multiple inventory locations")

    for row in events:
        day, aircraft, serial, kind = row["day"], row["aircraft"], row["serial"], row["event"]
        detail = json.loads(row["detail"]) if isinstance(row["detail"], str) else row["detail"]
        if pending_failure is not None:
            expected_day, expected_aircraft, expected_serial = pending_failure
            if (kind, day, aircraft, serial) != ("failure", expected_day, expected_aircraft, expected_serial):
                flag("failure_boundary", expected_day, "Flight at failure limit lacks immediate failure/AOG transition")
            pending_failure = None
        if last_day is not None and day < last_day:
            flag("ordering", day, "Events are not chronologically ordered")
        if day != last_day and last_day is not None:
            conserve(last_day)
        last_day = day
        if kind == "init_installed":
            if serial in installed.values():
                flag("serial_unique", day, "Duplicate installed serial")
            installed[aircraft], cycles[serial], states[aircraft] = serial, detail["cycle"], "serviceable"
        elif kind == "init_stock":
            if serial in stock or serial in installed.values():
                flag("serial_unique", day, "Duplicate initial stock serial")
            stock.add(serial)
            cycles[serial] = detail["cycle"]
        elif kind == "shop_return":
            if serial not in shop or shop.get(serial) != day:
                flag("conservation", day, "Unexpected shop return")
            shop.pop(serial, None)
            fresh = detail["new_serial"]
            if fresh in stock or fresh in installed.values() or fresh in shop:
                flag("serial_unique", day, "New serial is already active")
            stock.add(fresh)
            cycles[fresh] = 0
        elif kind == "start":
            starts[day] += 1
            if starts[day] > scenario["capacity"]:
                flag("capacity", day, "Too many starts")
            if serial not in stock:
                flag("spare", day, "Start has no serviceable spare")
            stock.discard(serial)
            removed = detail["removed"]
            if installed.get(aircraft) != removed:
                flag("serial_unique", day, "Removed serial was not installed here")
            if serial in installed.values() and installed.get(aircraft) != serial:
                flag("serial_unique", day, "Spare already installed elsewhere")
            expected = scenario["unplanned_downtime"] if detail["kind"] == "unplanned" else scenario["planned_downtime"]
            if detail["duration"] != expected or detail["end"] != day + expected - 1:
                flag("duration", day, "Wrong inclusive maintenance duration")
            if detail["kind"] == "unplanned" and states.get(aircraft) != "AOG":
                flag("unplanned", day, "Unplanned start before failure")
            if detail["kind"] == "planned":
                true_remaining = failure_cycles[scenario["serials"][removed]] - cycles.get(removed, -1)
                if detail["wasted_life"] != true_remaining:
                    flag("wasted_life", day, "Wrong wasted-life record")
            shop[removed] = day + scenario["turnaround"]
            installed[aircraft], states[aircraft] = serial, "maintenance"
            maintenance[aircraft] = (day, day + expected - 1)
        elif kind == "fly":
            if installed.get(aircraft) != serial:
                flag("serial_unique", day, "Flying serial not installed")
            if states.get(aircraft) != "serviceable":
                flag("grounded_flight", day, "Flight while unserviceable")
            if detail["before"] != cycles.get(serial) or detail["after"] != detail["before"] + detail["cycles"]:
                flag("cycles", day, "Cycle continuity broken")
            if detail["cycles"] < 0 or detail["before"] < 0 or detail["after"] < detail["before"]:
                flag("cycles", day, "Negative flight or cycle")
            if detail["cycles"] > scenario["demand"][day][aircraft]:
                flag("demand", day, "Flight exceeds requested demand")
            if detail["after"] > failure_cycles[scenario["serials"][serial]]:
                flag("failure_boundary", day, "Engine flew beyond failure cycle")
            cycles[serial] = detail["after"]
            if detail["after"] == failure_cycles[scenario["serials"][serial]]:
                pending_failure = (day, aircraft, serial)
        elif kind == "failure":
            if cycles.get(serial) != failure_cycles[scenario["serials"][serial]]:
                flag("failure_boundary", day, "Failure at wrong cycle")
            states[aircraft] = "AOG"
        elif kind == "complete":
            if aircraft not in maintenance or maintenance[aircraft][1] != day:
                flag("duration", day, "Completion at wrong day")
            completions.add((aircraft, day))
        elif kind == "serviceable":
            if aircraft not in maintenance or day != maintenance[aircraft][1] + 1:
                flag("duration", day, "Return to service at wrong day")
            if aircraft in maintenance and (aircraft, maintenance[aircraft][1]) not in completions:
                flag("duration", day, "Return to service without completion")
            states[aircraft] = "serviceable"
            maintenance.pop(aircraft, None)
        elif kind == "request":
            if installed.get(aircraft) != serial or states.get(aircraft) != "serviceable":
                flag("request", day, "Planned request from an unserviceable or different engine")
        else:
            flag("unknown_event", day, kind)
        if len(set(installed.values())) != len(installed):
            flag("serial_unique", day, "Serial installed twice")
    conserve(last_day)
    if pending_failure is not None:
        flag("failure_boundary", pending_failure[0], "Missing terminal failure/AOG event")
    for aircraft, (_, end) in maintenance.items():
        if end < scenario["days"] and (aircraft, end) not in completions:
            flag("duration", end, "Missing maintenance completion")
    for serial, requested, current in firewall:
        if requested > current:
            flag("future_access", -1, f"Future access by {serial}")
    return violations
