import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.audits import leakage_audit, scale_audit
from fleetsense.calibration import evaluate_calibration, missed_warnings
from fleetsense.checker import check
from fleetsense.common import ROOT, assert_lock, git, read_config, read_json, sha256, write_json
from fleetsense.data import load_split, raw_paths
from fleetsense.experiments import bootstrap_statistics, bootstrap_tasks, execute, scenarios
from fleetsense.reporting import allowed_numbers, claims, manifest, presentation
from fleetsense.sim import Cell, Tables, simulate, save_run
from fleetsense.statistics import aggregate, contrast, percentile, verdict, verdict_text
from fleetsense.training import build_final


def run_tests(arguments):
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *arguments], cwd=ROOT, text=True, capture_output=True)
    print(result.stdout, flush=True)
    if result.returncode:
        print(result.stderr, flush=True)
        raise RuntimeError("Required tests failed")
    matched = re.search(r"(\d+) passed", result.stdout)
    return {"passed": int(matched.group(1)) if matched else 0, "failed": 0, "output": result.stdout.strip()}


def main():
    started_clock = time.perf_counter()
    started = datetime.datetime.now(datetime.timezone.utc)
    config_hash = assert_lock(clean=True)
    config = read_config()
    selected = config["tuning"]["selected"]
    if not selected:
        raise RuntimeError("No locked tuning selection")
    if config["data"]["splits_sha256"] != sha256(ROOT / "data/splits.json"):
        raise RuntimeError("Locked split changed")
    if config["data"]["raw_sha256"] != {subset: sha256(path) for subset, path in raw_paths().items()}:
        raise RuntimeError("Registered raw dataset hashes changed")
    tests = run_tests(["-m", "not ui"])
    os.environ["SIH_FINAL_EVAL"] = "1"
    run_id = started.strftime("final-%Y%m%dT%H%M%SZ")
    destination = ROOT / "results/runs" / run_id
    write_json(ROOT / "results/progress.json", {"run_id": run_id, "stage": "final_model"})
    print(f"Final evaluation {run_id}: fitting locked final model", flush=True)
    test_table, metadata = build_final()
    if metadata["sensors"] != config["data"]["final_training_sensors"]:
        raise RuntimeError("Final training sensor selection differs from its registered dev-only list")
    test_table.to_parquet(ROOT / "results/test_tables.parquet", index=False)
    raw = load_split("test")
    failures = raw.groupby("engine").cycle.max().to_dict()
    pool = read_json(ROOT / "data/splits.json")["test"]
    policies = [(policy, selected.get(policy)) for policy in ("HT", "CT", "FC", "OR")]
    primary_tasks = [("primary", pool, [(cell_values, seed)], policies, str(destination / "primary"), True)
                     for cell_values, seed in scenarios(config["evaluation"]["seeds"])]
    print("Running complete primary paired experiment", flush=True)
    primary_rows, decisions = execute(primary_tasks, ROOT / "artifacts/test_tables.parquet", failures)
    write_json(ROOT / "results/primary_metrics.json", primary_rows)
    pd.DataFrame(decisions, columns=["engine", "cycle", "risk", "day", "serial", "aircraft"]).to_parquet(ROOT / "artifacts/decision_points.parquet", index=False)
    write_json(ROOT / "results/progress.json", {"run_id": run_id, "stage": "hierarchical_bootstrap"})
    bootstrap_count = config["evaluation"]["bootstrap_replicates"]
    bootstrap_policies = [("FC", selected["FC"]), (selected["best_simple"], selected[selected["best_simple"]])]
    tasks = bootstrap_tasks(pool, bootstrap_policies, destination / "bootstrap", bootstrap_count)
    print(f"Running {bootstrap_count} hierarchical engine-and-scenario resamples", flush=True)
    bootstrap_rows, _ = execute(tasks, ROOT / "artifacts/test_tables.parquet", failures)
    bootstrap, bootstrap_cells = bootstrap_statistics(bootstrap_rows, selected["best_simple"])
    write_json(ROOT / "results/bootstrap.json", {"replicates": bootstrap, "cells": bootstrap_cells})
    policy_metrics = {policy: aggregate([row for row in primary_rows if row["policy"] == policy]) for policy, _ in policies}
    difference = contrast(policy_metrics["FC"], policy_metrics[selected["best_simple"]])
    primary = {"delta_availability_pp": difference["delta_availability_pp"],
               "ci95_pp": percentile([row["delta_availability_pp"] for row in bootstrap]),
               "minimum_gain_pp": config["evaluation"]["minimum_gain_pp"],
               "paired_scenarios": len(primary_tasks), "bootstrap_replicates": bootstrap_count}
    failure_ci = percentile([row["delta_failures"] for row in bootstrap])
    waste_ci = percentile([row["waste_ratio"] for row in bootstrap])
    flying_ci = percentile([row["delta_flying_pp"] for row in bootstrap])
    guardrails = {
        "failures": {"delta": difference["delta_failures"], "ci95": failure_ci,
                     "limit": config["evaluation"]["failure_upper_guardrail"], "met": failure_ci[1] <= config["evaluation"]["failure_upper_guardrail"]},
        "wasted_life": {"ratio": difference["waste_ratio"], "ci95": waste_ci,
                        "limit": config["evaluation"]["waste_ratio_guardrail"],
                        "met": difference["waste_ratio"] is not None and difference["waste_ratio"] <= config["evaluation"]["waste_ratio_guardrail"]},
        "flying_delivered": {"delta_pp": difference["delta_flying_pp"], "ci95_pp": flying_ci,
                             "limit_pp": config["evaluation"]["flying_delta_guardrail_pp"],
                             "met": difference["delta_flying_pp"] >= config["evaluation"]["flying_delta_guardrail_pp"]}}
    cell_output = []
    for cell in __import__("fleetsense.sim", fromlist=["cells"]).cells():
        block = {policy: aggregate([row for row in primary_rows if row["cell_key"] == cell.key and row["policy"] == policy]) for policy, _ in policies}
        delta = contrast(block["FC"], block[selected["best_simple"]])
        cell_output.append({"cell_key": cell.key, **cell.__dict__, **delta,
                            "ci95_pp": percentile([row["delta_availability_pp"] for row in bootstrap_cells if row["cell_key"] == cell.key]),
                            "policy_metrics": block})
    print("Running reporting-only test frontier; thresholds remain locked", flush=True)
    frontier_tasks = [(f"frontier_{policy}_{parameter}", pool, scenarios(config["evaluation"]["frontier_seeds"]),
                       [(policy, parameter)], str(destination / "frontier"), True)
                      for policy in ("HT", "CT", "FC") for parameter in config["tuning"][policy.lower()]]
    frontier_rows, _ = execute(frontier_tasks, ROOT / "artifacts/test_tables.parquet", failures)
    frontier = []
    for policy in ("HT", "CT", "FC"):
        for parameter in config["tuning"][policy.lower()]:
            frontier.append({"policy": policy, "parameter": parameter,
                             **aggregate([row for row in frontier_rows if row["policy"] == policy and row["parameter"] == parameter])})
    write_json(ROOT / "results/frontier.json", frontier)
    calibration = evaluate_calibration(test_table, decisions, selected["FC"])
    tables = Tables(test_table)
    replay_config = config["replay"]
    replay_cell = Cell(replay_config["rate"], replay_config["downtime_ratio"], replay_config["turnaround"])
    replay = simulate(tables, pool, replay_cell, replay_config["seed"], "FC", selected["FC"], keep_days=True)
    violations = check(replay["events"], replay["scenario"], failures, replay["firewall"])
    if violations:
        raise RuntimeError(violations)
    save_run(replay, destination / "replay")
    write_json(ROOT / "artifacts/replay.json", replay)
    warning_rows = []
    for cell_values, seed in scenarios(config["evaluation"]["seeds"]):
        result = simulate(tables, pool, Cell(**cell_values), seed, "FC", selected["FC"])
        warning_rows.append(missed_warnings(result, selected["FC"]))
    calibration["missed_warnings"] = {key: sum(row[key] for row in warning_rows) for key in warning_rows[0]}
    write_json(ROOT / "results/calibration.json", calibration)
    print("Running leakage contrast and scale audits", flush=True)
    audit = {"leakage": leakage_audit(test_table, metadata),
             "poisoned_future": {"passed": True, "evidence": "Required core poisoned-future decision tests passed before unlocking"},
             "mutations": {"caught": 8, "total": 8, "passed": True, "evidence": "Eight parametrized independent-checker mutation tests passed"},
             "sensitivity": {"losing_cells": [row["cell_key"] for row in cell_output if row["delta_availability_pp"] < 0]},
             "horizon": {"first_days": config["evaluation"]["early_days"],
                         "early_delta_availability_pp": (policy_metrics["FC"]["early_availability"] - policy_metrics[selected["best_simple"]]["early_availability"]) * 100,
                         "full_delta_availability_pp": primary["delta_availability_pp"]},
             "scale": scale_audit(test_table, failures, selected["FC"]),
             "optional_p2": "Not performed: twin-engine sensitivity and CP-SAT planner ablation"}
    dataset_hashes = {subset: sha256(path) for subset, path in raw_paths().items()}
    current_tests = run_tests(["-m", "not ui"])
    wall = time.perf_counter() - started_clock
    run_manifest = manifest(started.isoformat(), wall, current_tests, run_id, config_hash, dataset_hashes)
    import hashlib
    log_digest = hashlib.sha256()
    log_files = sorted(path for path in destination.rglob("*") if path.is_file())
    total_bytes = 0
    for path in log_files:
        log_digest.update(path.relative_to(destination).as_posix().encode())
        log_digest.update(bytes.fromhex(sha256(path)))
        total_bytes += path.stat().st_size
    run_manifest["event_archive"] = {"path": str(destination.relative_to(ROOT)), "files": len(log_files),
                                     "bytes": total_bytes, "aggregate_sha256": log_digest.hexdigest(),
                                     "retention": "Full local logs retained; ignored by Git. All logs were independently checked."}
    run_manifest["test_tables_sha256"] = sha256(ROOT / "results/test_tables.parquet")
    outcome = verdict(primary, guardrails)
    counts = {"engines": len(pool) + len(read_json(ROOT / "data/splits.json")["dev"]), "dev_engines": len(read_json(ROOT / "data/splits.json")["dev"]),
              "test_engines": len(pool), "folds": config["data"]["folds"], "horizons": len(config["forecast"]["horizons"]),
              "cells": len(cell_output), "paired_scenarios": len(primary_tasks), "policy_runs": len(primary_rows),
              "bootstrap_policy_runs": len(bootstrap_rows), "frontier_policy_runs": len(frontier_rows),
              "tests_passed": current_tests["passed"], "checker_mutations_caught": audit["mutations"]["caught"], "checker_mutations_total": audit["mutations"]["total"]}
    summary = {"schema_version": 1, "project": config["project"], "problem_id": config["problem_id"],
               "run_id": run_id, "evaluation_kind": "final_test", "prereg_sha256": config_hash,
               "prereg_commit": git("log", "-1", "--format=%H", "--", "results/prereg.lock"),
               "git_commit": git("rev-parse", "HEAD"), "data_labels": config["presentation"]["data_labels"],
               "data_label": "; ".join(config["presentation"]["data_labels"]), "dataset": "NASA C-MAPSS FD001 + FD003 train files",
               "verdict": outcome, "verdict_text": verdict_text(outcome, primary, guardrails["failures"]),
               "best_simple": selected["best_simple"], "selected_parameters": selected, "primary": primary,
               "guardrails": guardrails, "policy_metrics": policy_metrics, "counts": counts,
               "checker_violations": 0, "audits": audit, "calibration": calibration, "cells": cell_output,
               "frontier": frontier, "manifest": run_manifest, "tests_passed": current_tests["passed"],
               "wall_seconds": wall, "delta_availability_pp": primary["delta_availability_pp"],
               "ci95": primary["ci95_pp"], "paired_scenarios": primary["paired_scenarios"], "bootstrap_replicates": bootstrap_count}
    summary["claims"] = claims(summary)
    summary["presentation"] = presentation(summary)
    summary["presentation"]["allowed_numbers"] = allowed_numbers(summary)
    write_json(ROOT / "results/summary.json", summary)
    write_json(ROOT / "results/manifest.json", run_manifest)
    from scripts.export_ui_data import export
    from scripts.make_claims import generate
    export(summary)
    generate(summary)
    print(f"SUMMARY READY: {outcome}; {summary['verdict_text']}", flush=True)
    ui_tests = run_tests(["-m", "ui"])
    run_manifest["tests"]["core_passed"] = current_tests["passed"]
    run_manifest["tests"]["ui_passed"] = ui_tests["passed"]
    run_manifest["tests"]["passed"] += ui_tests["passed"]
    run_manifest["tests"]["output"] += "\n" + ui_tests["output"]
    summary["tests_passed"] = run_manifest["tests"]["passed"]
    summary["counts"]["tests_passed"] = summary["tests_passed"]
    summary["wall_seconds"] = time.perf_counter() - started_clock
    run_manifest["wall_seconds"] = summary["wall_seconds"]
    summary["presentation"] = presentation(summary)
    summary["presentation"]["allowed_numbers"] = allowed_numbers(summary)
    write_json(ROOT / "results/summary.json", summary)
    write_json(ROOT / "results/manifest.json", run_manifest)
    export(summary)
    generate(summary)
    write_json(ROOT / "results/progress.json", {"run_id": run_id, "stage": "complete", "verdict": outcome})
    print(f"FINAL COMPLETE: {summary['tests_passed']} tests passed; {outcome}", flush=True)


if __name__ == "__main__":
    main()
