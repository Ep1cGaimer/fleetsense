import math

import numpy as np


class EngineView:
    __slots__ = ("serial", "current_cycle", "age", "_rows", "_horizons", "_log", "cap_events")

    def __init__(self, serial, current_cycle, rows, horizons, log):
        self.serial = serial
        self.current_cycle = current_cycle
        self.age = current_cycle
        self._rows = rows[:current_cycle + 1].view()
        self._rows.flags.writeable = False
        self._horizons = horizons
        self._log = log
        self.cap_events = 0

    def row(self, requested=None):
        requested = self.current_cycle if requested is None else requested
        self._log.append((self.serial, requested, self.current_cycle))
        if requested > self.current_cycle:
            raise PermissionError("Future table access refused")
        if requested < 0:
            raise ValueError("Negative cycle")
        return self._rows[requested]

    def health(self):
        return float(self.row()[0])

    def risk(self, cycles):
        index = int(np.searchsorted(self._horizons, math.ceil(cycles)))
        if index == len(self._horizons):
            self.cap_events += 1
            index -= 1
        return float(self.row()[index + 1])


def request(policy, parameter, view, rate, lead):
    if policy == "HT":
        return view.age >= parameter, float(view.age)
    if policy == "CT":
        health = view.health()
        return health <= parameter, -health
    if policy == "FC":
        risk = view.risk(rate * lead)
        return risk >= parameter, risk
    raise ValueError("Oracle must use the explicitly privileged path")
