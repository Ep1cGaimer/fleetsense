import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from fleetsense.checker import check
from fleetsense.common import ROOT, read_config, write_json
from fleetsense.sim import Cell, Tables, cells, save_run, simulate
from fleetsense.statistics import aggregate, contrast

_TABLES = None
_FAILURES = None


def initialize_worker(table_path, failure_cycles):
    global _TABLES, _FAILURES
    _TABLES = Tables(pd.read_parquet(table_path))
    _FAILURES = failure_cycles


def run_batch(task):
    group, pool, scenarios, policies, destination, retain = task
    output, decision_points = [], []
    for cell_values, seed in scenarios:
        cell = Cell(**cell_values)
        for policy, parameter in policies:
            result = simulate(_TABLES, pool, cell, seed, policy, parameter)
            violations = check(result["events"], result["scenario"], _FAILURES, result["firewall"])
            if violations:
                write_json(ROOT / "results/checker_failure.json", {"group": group, "violations": violations[:50]})
                raise RuntimeError(f"Independent checker rejected {group}/{policy}: {violations[:2]}")
            if retain:
                name = f"{group}_{cell.key.replace('.', 'p')}_seed{seed}_{policy}_{parameter}"
                save_run(result, Path(destination) / name)
            output.append({"group": group, "cell": cell.__dict__, "cell_key": cell.key, "seed": seed,
                           "policy": policy, "parameter": parameter, **result["metrics"]})
            if group == "primary" and policy == "FC":
                decision_points.extend(result["decisions"])
    return output, decision_points


def execute(tasks, table_path, failure_cycles, workers=None):
    workers = workers or read_config()["evaluation"]["workers"]
    rows, decisions = [], []
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize_worker,
                             initargs=(str(table_path), failure_cycles)) as executor:
        for index, (batch, points) in enumerate(executor.map(run_batch, tasks)):
            rows.extend(batch)
            decisions.extend(points)
            if (index + 1) % 10 == 0 or index + 1 == len(tasks):
                print(f"Simulation batches {index + 1}/{len(tasks)}", flush=True)
    return rows, decisions


def scenarios(seeds):
    return [(cell.__dict__, int(seed)) for cell in cells() for seed in seeds]


def bootstrap_tasks(pool, policies, destination, replicates, retain=True):
    config = read_config()["evaluation"]
    generator = np.random.default_rng(config["bootstrap_seed"])
    tasks = []
    for replicate in range(replicates):
        sampled = generator.choice(pool, size=len(pool), replace=True).tolist()
        seeds = generator.integers(10000, 2**31 - 1, size=config["bootstrap_seeds_per_cell"]).tolist()
        tasks.append((f"bootstrap{replicate:04d}", sampled, scenarios(seeds), policies, str(destination), retain))
    return tasks


def bootstrap_statistics(rows, best_simple):
    frame = pd.DataFrame(rows)
    global_rows, cell_rows = [], []
    for group, block in frame.groupby("group", sort=True):
        policy = {name: aggregate(subset.to_dict("records")) for name, subset in block.groupby("policy")}
        global_rows.append({"replicate": group, **contrast(policy["FC"], policy[best_simple])})
        for cell_key, cell_block in block.groupby("cell_key"):
            cell_policy = {name: aggregate(subset.to_dict("records")) for name, subset in cell_block.groupby("policy")}
            cell_rows.append({"replicate": group, "cell_key": cell_key, **contrast(cell_policy["FC"], cell_policy[best_simple])})
    return global_rows, cell_rows


def time_bootstrap(table_path, failures, pool, policies):
    started = time.perf_counter()
    tasks = bootstrap_tasks(pool, policies, ROOT / "results/dev/dry", 4, retain=True)
    rows, _ = execute(tasks, table_path, failures, workers=4)
    elapsed = time.perf_counter() - started
    statistics, _ = bootstrap_statistics(rows, policies[1][0])
    return {"replicates_timed": len(tasks), "policy_runs": len(rows), "wall_seconds": elapsed,
            "estimated_500_seconds": elapsed * 500 / len(tasks), "dry_kind": "dev_only_not_final",
            "bootstrap_values": statistics}
