def choose_starts(unplanned, planned, capacity, stock):
    limit = min(capacity, stock)
    urgent = sorted(unplanned, key=lambda request: (request["day"], request["aircraft"]))
    preventive = sorted(planned, key=lambda request: (-request["urgency"], request["aircraft"]))
    return (urgent + preventive)[:limit]
